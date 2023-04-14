#!/usr/bin/env python

########################################################################
# Copyright (c) 2020,2023 Robert Bosch GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0
########################################################################

"""
Feeder parsing CAN data and sending to KUKSA.val
"""

import enum
import logging
import os
import sys
import can
from signal import SIGINT, SIGTERM, signal

from canproviderlib import dbc2vssmapper
from canproviderlib import dbcreader

import asyncio

from kuksa_client.grpc.aio import VSSClient


log = logging.getLogger("canprovider")


class ServerType(str, enum.Enum):
    KUKSA_VAL_SERVER = 'kuksa_val_server'
    KUKSA_DATABROKER = 'kuksa_databroker'


def init_logging(loglevel):
    # create console handler and set level to debug
    console_logger = logging.StreamHandler()
    console_logger.setLevel(logging.DEBUG)

    # create formatter
    if sys.stdout.isatty():
        formatter = ColorFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s"
        )

    # add formatter to console_logger
    console_logger.setFormatter(formatter)

    # add console_logger as a global handler
    root_logger = logging.getLogger()
    root_logger.setLevel(loglevel)
    root_logger.addHandler(console_logger)


class ColorFormatter(logging.Formatter):
    FORMAT = "{time} {{loglevel}} {logger} {msg}".format(
        time="\x1b[2m%(asctime)s\x1b[0m",  # grey
        logger="\x1b[2m%(name)s:\x1b[0m",  # grey
        msg="%(message)s",
    )
    FORMATS = {
        logging.DEBUG: FORMAT.format(loglevel="\x1b[34mDEBUG\x1b[0m"),  # blue
        logging.INFO: FORMAT.format(loglevel="\x1b[32mINFO\x1b[0m"),  # green
        logging.WARNING: FORMAT.format(loglevel="\x1b[33mWARNING\x1b[0m"),  # yellow
        logging.ERROR: FORMAT.format(loglevel="\x1b[31mERROR\x1b[0m"),  # red
        logging.CRITICAL: FORMAT.format(loglevel="\x1b[31mCRITICAL\x1b[0m"),  # red
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class Feeder:

    def __init__(self):
        self._shutdown = False
        self.bus = can.interface.Bus(bustype="socketcan",
                                     channel="vcan0", bitrate=500000)  # pylint: disable=abstract-class-instantiated

    async def start(self):

        log.info("Using DBC reader")
        self._reader = dbcreader.DBCReader(
                dbcfile="Model3CAN.dbc"
            )

        mappingfile = "mapping/vss_3.1.1/vss_dbc.json"
        log.info("Using mapping: {}".format(mappingfile))
        self._mapper = dbc2vssmapper.Mapper(mappingfile, self._reader)
        subscribe_entries = self._mapper.get_subscribe_entries()

        async with VSSClient('127.0.0.1', 55555) as client:
            async for updates in client.subscribe(entries=subscribe_entries):
                log.debug(f"Received update of length {len(updates)}")
                dbc_ids = set()
                for update in updates:
                    if update.entry.value is not None:
                        # This shall currently never happen as we do not subscribe to this
                        log.warning(f"Current value for {update.entry.path} is now: "
                                    f"{update.entry.value.value} of type {type(update.entry.value.value)}")

                    if update.entry.actuator_target is not None:
                        log.info(f"Target value for {update.entry.path} is now: {update.entry.actuator_target}"
                                 f" of type {type(update.entry.actuator_target.value)}")
                        new_dbc_ids = self._mapper.handle_update(update.entry.path, update.entry.actuator_target.value)
                        dbc_ids.update(new_dbc_ids)

                can_ids = set()
                for dbc_id in dbc_ids:
                    can_id = self._reader.get_canid_for_signal(dbc_id)
                    can_ids.add(can_id)

                for can_id in can_ids:
                    if can_id == 258:
                        log.info(f"Supported CAN id to be sent, this is {can_id}")
                        sig_dict = self._mapper.get_value_dict(can_id)
                        message_data = self._reader.get_message_by_frame_id(can_id)
                        data = message_data.encode(sig_dict)
                        msg = can.Message(arbitration_id=message_data.frame_id, data=data)
                        try:
                            self.bus.send(msg)
                            log.debug(f"Message sent on {self.bus.channel_info}")
                            log.debug(f"Message: {msg}")
                        except can.CanError:
                            log.error("Failed to send message via CAN bus")
                    else:
                        # We only have default handling for 258
                        log.info(f"Currently only can_id 258 is sent, this is {can_id}")

    def stop(self):
        log.info("Shutting down...")
        self._shutdown = True

    def is_stopping(self):
        return self._shutdown


async def main(argv):

    feeder = Feeder()

    def signal_handler(signal_received, frame):
        log.info(f"Received signal {signal_received}, stopping...")

        # If we get told to shutdown a second time. Just do it.
        if feeder.is_stopping():
            log.warning("Shutdown now!")
            sys.exit(-1)

        feeder.stop()

    signal(SIGINT, signal_handler)
    signal(SIGTERM, signal_handler)

    log.info("Starting CAN feeder")
    await feeder.start()

    return 0


def parse_env_log(env_log, default=logging.INFO):
    def parse_level(level, default=default):
        if type(level) is str:
            if level.lower() in [
                "debug",
                "info",
                "warn",
                "warning",
                "error",
                "critical",
            ]:
                return level.upper()
            else:
                raise Exception(f"could not parse '{level}' as a log level")
        return default

    loglevels = {}

    if env_log is not None:
        log_specs = env_log.split(",")
        for log_spec in log_specs:
            spec_parts = log_spec.split("=")
            if len(spec_parts) == 1:
                # This is a root level spec
                if "root" in loglevels:
                    raise Exception("multiple root loglevels specified")
                else:
                    loglevels["root"] = parse_level(spec_parts[0])
            if len(spec_parts) == 2:
                logger = spec_parts[0]
                level = spec_parts[1]
                loglevels[logger] = parse_level(level)

    if "root" not in loglevels:
        loglevels["root"] = default

    return loglevels


if __name__ == "__main__":
    # Example
    #
    # Set log level to debug
    #   LOG_LEVEL=debug ./dbcfeeder.py
    #
    # Set log level to INFO, but for dbcfeeder.broker set it to DEBUG
    #   LOG_LEVEL=info,dbcfeeder.broker_client=debug ./dbcfeeder.py
    #
    # Other available loggers:
    #   dbcfeeder
    #   dbcfeeder.broker_client
    #   databroker (useful for feeding values debug)
    #   dbcreader
    #   dbcmapper
    #   can
    #   j1939
    #

    loglevels = parse_env_log(os.environ.get("LOG_LEVEL"))

    # set root loglevel etc
    init_logging(loglevels["root"])

    # set loglevels for other loggers
    for logger, level in loglevels.items():
        if logger != "root":
            logging.getLogger(logger).setLevel(level)

    asyncio.run(main(sys.argv))
