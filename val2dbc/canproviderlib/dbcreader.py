#!/usr/bin/python3

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

import cantools
import logging

log = logging.getLogger(__name__)


class DBCReader:
    def __init__(self, dbcfile: str, use_strict_parsing=True):
        log.info("Reading DBC file {}".format(dbcfile))
        self.db = cantools.database.load_file(dbcfile, strict=use_strict_parsing)

    def get_canid_for_signal(self, sig_to_find):
        for msg in self.db.messages:
            for signal in msg.signals:
                if signal.name == sig_to_find:
                    id = msg.frame_id
                    log.info(
                        "Found signal in DBC file {} in CAN frame id 0x{:02x}".format(
                            signal.name, id
                        )
                    )
                    return id
        log.warning("Signal {} not found in DBC file".format(sig_to_find))
        return None

    def get_message_by_frame_id(self, can_id):
        return self.db.get_message_by_frame_id(can_id)
