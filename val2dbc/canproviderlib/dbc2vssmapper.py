#!/usr/bin/python3

########################################################################
# Copyright (c) 2020 Robert Bosch GmbH
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
Classes for maintaining mapping between dbc and VSS
as well as transforming dbc data to VSS data.
"""

import json
import logging
import sys
from typing import Any, Dict, List, Set

from py_expression_eval import Parser
from kuksa_client.grpc import Field
from kuksa_client.grpc import SubscribeEntry
from kuksa_client.grpc import View
from canproviderlib import dbcreader

log = logging.getLogger(__name__)


class VSSMapping:
    """A mapping for a VSS signal"""

    parser: Parser = Parser()

    def __init__(self, dbc_name: str, transform: dict):
        self.dbc_name = dbc_name
        self.transform = transform
        # For time comparison (interval_ms) we store last value used for comparison. Unit seconds.
        self.last_time: float = 0.0
        # For value comparison (on_changes) we store last value used for comparison
        self.last_dbc_value: Any = None

    def transform_value(self, value: Any) -> Any:
        """
        Transforms the given VSS value to the wanted "raw" DBC value.
        For now does not make any type checks
        Only type of value checked so far is int and bool
        """
        dbc_value = None
        if self.transform is None:
            log.debug(f"No mapping to DBC {self.dbc_name}, using VSS value {value}")
            dbc_value = value
        else:
            if "mapping" in self.transform:
                tmp = self.transform["mapping"]
                # Assumed to be a list
                for item in tmp:
                    from_val = item["from"]
                    if from_val == value:
                        new_val = item["to"]
                        dbc_value = new_val
                        break
            elif "math" in self.transform:
                tmp = self.transform["math"]
                try:
                    dbc_value = VSSMapping.parser.parse(tmp).evaluate({"x": value})
                except Exception:
                    # It is assumed that you may consider it ok that transformation fails sometimes,
                    # so giving warning instead of error
                    # This could be e.g. trying to treat a string as int
                    log.warning(f"Transformation failed for value {value} "
                                f"for DBC signal {self.dbc_name}, signal ignored!", exc_info=True)
            else:
                # It is supposed that "extract_verify_transform" already have checked that
                # we have a valid transform, so we shall never end up here
                log.error("Unsupported transform")

        if dbc_value is None:
            log.info(f"No mapping to DBC {self.dbc_name} found for VSS value {value},"
                     f"returning None to indicate that it shall be ignored!")
        else:
            log.debug(f"Transformed value {dbc_value} for {self.dbc_name}")
        return dbc_value


class Mapper:
    """
    The mapper class contain all mappings between dbc and vss.
    It also contain functionality for transforming data
    """

    # Where we keep mapping, key is vss signal name
    mapping: Dict[str, List[VSSMapping]] = {}
    # Same, but key is CAN id mapping
    can_id_mapping: Dict[int, List[VSSMapping]] = {}

    def extract_verify_transform(self, expanded_name: str, node: dict):
        """
        Extracts transformation and checks it seems to be correct
        """
        if "transform" not in node:
            log.debug(f"No transformation found for {expanded_name}")
            # For now assumed that None is Ok
            return None
        transform = node["transform"]

        has_mapping = False

        if not isinstance(transform, dict):
            log.error(f"Transform not dict for {expanded_name}")
            sys.exit(-1)
        if "mapping" in transform:
            tmp = transform["mapping"]
            if not isinstance(tmp, list):
                log.error(f"Transform mapping not list for {expanded_name}")
                sys.exit(-1)
            for item in tmp:
                if not (("from" in item) and ("to" in item)):
                    log.error(f"Mapping missing to and from in {item} for {expanded_name}")
                    sys.exit(-1)
            has_mapping = True

        if "math" in transform:
            if has_mapping:
                log.error(f"Can not have both mapping and math for {expanded_name}")
                sys.exit(-1)
            if not isinstance(transform["math"], str):
                log.error(f"Math must be str for {expanded_name}")
                sys.exit(-1)
        elif not has_mapping:
            log.error(f"Unsupported transform for {expanded_name}")
            sys.exit(-1)
        return transform

    def analyze_signal(self, expanded_name, node):
        """
        Analyzes a signal and add mapping entry if correct mapping found
        """
        if "vss2dbc" in node:
            log.debug(f"Signal {expanded_name} has vss2dbc!")
            dbc_def = node["vss2dbc"]
            transform = self.extract_verify_transform(expanded_name, dbc_def)
            dbc_name = dbc_def.get("signal", "")
            if dbc_name == "":
                log.error(f"No dbc signal found for {expanded_name}")
                sys.exit(-1)
            mapping_entry = VSSMapping(dbc_name, transform)
            if expanded_name not in self.mapping:
                self.mapping[expanded_name] = []
            self.mapping[expanded_name].append(mapping_entry)

            # Also add CAN-id
            can_id = self.reader.get_canid_for_signal(dbc_name)
            if can_id not in self.can_id_mapping:
                self.can_id_mapping[can_id] = []
            self.can_id_mapping[can_id].append(mapping_entry)

    def get_default_values(self, can_id) -> Dict[int, Any]:
        res = {}
        # All signals must have a value, first add default values for all signals for our example mapping
        # This could possibly be read from a config file
        if can_id == 258:
            res['VCLEFT_frontHandlePWM'] = 0
            res['VCLEFT_frontHandlePulled'] = 0
            res['VCLEFT_frontHandlePulledPersist'] = 0
            res['VCLEFT_frontIntSwitchPressed'] = 0
            res['VCLEFT_frontLatchStatus'] = 0
            res['VCLEFT_frontLatchSwitch'] = 0
            res['VCLEFT_frontRelActuatorSwitch'] = 0
            res['VCLEFT_mirrorDipped'] = 0
            res['VCLEFT_mirrorFoldState'] = 0
            res['VCLEFT_mirrorHeatState'] = 0
            res['VCLEFT_mirrorRecallState'] = 0
            res['VCLEFT_mirrorState'] = 0
            res['VCLEFT_mirrorTiltXPosition'] = 0
            res['VCLEFT_mirrorTiltYPosition'] = 0
            res['VCLEFT_rearHandlePWM'] = 0
            res['VCLEFT_rearHandlePulled'] = 0
            res['VCLEFT_rearIntSwitchPressed'] = 0
            res['VCLEFT_rearLatchStatus'] = 0
            res['VCLEFT_rearLatchSwitch'] = 0
            res['VCLEFT_rearRelActuatorSwitch'] = 0

            return res

    def get_value_dict(self, can_id):

        log.debug(f"Using stored information to create CAN-frame for {can_id}")
        res = self.get_default_values(can_id)

        for can_mapping in self.can_id_mapping[can_id]:
            log.info(f"Using DBC id {can_mapping.dbc_name} with value {can_mapping.last_dbc_value}")
            if can_mapping.last_dbc_value is not None:
                res[can_mapping.dbc_name] = can_mapping.last_dbc_value
        return res

    def traverse_vss_node(self, name, node, prefix=""):
        """
        Traverse a vss node/tree and order all found VSS signals to be analyzed
        so that mapping can be extracted
        """
        is_signal = False
        is_branch = False
        expanded_name = ""
        if isinstance(node, dict):
            if "type" in node:
                if node["type"] in ["sensor", "actuator", "attribute"]:
                    is_signal = True
                elif node["type"] in ["branch"]:
                    is_branch = True
                    prefix = prefix + name + "."

        # Assuming it to be a dict
        if is_branch:
            for item in node["children"].items():
                self.traverse_vss_node(item[0], item[1], prefix)
        elif is_signal:
            expanded_name = prefix + name
            self.analyze_signal(expanded_name, node)
        elif isinstance(node, dict):
            for item in node.items():
                self.traverse_vss_node(item[0], item[1], prefix)

    def get_subscribe_entries(self):
        entries = []
        for key in self.mapping.keys():
            log.info(f"Subscribing to {key}")
            # Always subscribe to target
            subscribe_entry = SubscribeEntry(key, View.FIELDS, [Field.ACTUATOR_TARGET])
            entries.append(subscribe_entry)
        return entries

    def handle_update(self, vss_name, value: Any) -> Set[str]:
        """
        Finds dbc signals using this VSS-signal, transform value accordingly
        and updated stored value.
        Returns set of affected CAN signal identifiers.
        Types of values tested so far: int, bool
        """
        dbc_ids = set()
        # Theoretically there might me multiple DBC-signals served by this VSS-signal
        for dbc_mapping in self.mapping[vss_name]:

            dbc_value = dbc_mapping.transform_value(value)
            dbc_mapping.last_dbc_value = dbc_value
            dbc_ids.add(dbc_mapping.dbc_name)
        return dbc_ids

    def __init__(self, filename, reader: dbcreader.DBCReader):
        with open(filename, "r") as file:
            try:
                jsonmapping = json.load(file)
                log.info(f"Reading dbc configurations from {filename}")
            except Exception:
                log.error(f"Failed to read json from {filename}", exc_info=True)
                sys.exit(-1)

        self.reader = reader
        self.traverse_vss_node("", jsonmapping)

    def map(self):
        """ Get access to the map items """
        return self.mapping.items()

    def __contains__(self, key):
        return key in self.mapping

    def __getitem__(self, item):
        return self.mapping[item]
