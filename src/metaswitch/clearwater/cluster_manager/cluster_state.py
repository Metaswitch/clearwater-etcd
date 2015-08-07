#!/usr/bin/python

# Project Clearwater - IMS in the Cloud
# Copyright (C) 2015 Metaswitch Networks Ltd
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version, along with the "Special Exception" for use of
# the program along with SSL, set forth below. This program is distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details. You should have received a copy of the GNU General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
# The author can be reached by email at clearwater@metaswitch.com or by
# post at Metaswitch Networks Ltd, 100 Church St, Enfield EN2 6BQ, UK
#
# Special Exception
# Metaswitch Networks Ltd  grants you permission to copy, modify,
# propagate, and distribute a work formed by combining OpenSSL with The
# Software, or a work derivative of such a combination, even if such
# copying, modification, propagation, or distribution would otherwise
# violate the terms of the GPL. You must comply with the GPL in all
# respects for all of the code used other than OpenSSL.
# "OpenSSL" means OpenSSL toolkit software distributed by the OpenSSL
# Project and licensed under the OpenSSL Licenses, or a work based on such
# software and licensed under the OpenSSL Licenses.
# "OpenSSL Licenses" means the OpenSSL License and Original SSLeay License
# under which the OpenSSL Project distributes the OpenSSL toolkit software,
# as those licenses appear in the file LICENSE-OPENSSL.

import json
from collections import defaultdict

import constants
import logging

_log = logging.getLogger(__name__)

class ClusterInfo(object):
    def __init__(self, value):
        self.view = {}
        try:
            self.view = json.loads(value)
        except:
            pass

        self.cluster_state = self.calculate_cluster_state(self.view)


    def can_leave(self, allow_errors=False):
        return self.cluster_state == constants.STABLE or \
               self.cluster_state == constants.LEAVE_PENDING or \
                (allow_errors and
                 self.cluster_state == constants.STABLE_WITH_ERRORS)

    # Calculate the state of the cluster based on the state of all the nodes in
    # the cluster.
    def calculate_cluster_state(self, cluster_view):
        # Create a default dictionary. The default value of any key is 0.
        node_state_counts = defaultdict(int)
        node_states = cluster_view.values()
        node_count = 0
        error_count = 0

        # Count the number of nodes in each state. This will make working out
        # the state of the cluster below easier.
        for state in node_states:
            node_state_counts[state] += 1

            # Count the total number of nodes in the cluster. Ignore nodes in
            # ERROR state.
            if state != constants.ERROR:
                node_count += 1
            else:
                error_count += 1

        # Checks the contents of node_states: returns True if
        # - at least one node is in one of the states in oneOrMore, and
        # - all nodes are in one of the states on oneOrMore, zeroOrMore, or
        #   ERROR
        def state_check(zeroOrMore=None, oneOrMore=None):
            if not zeroOrMore:
                zeroOrMore = []
            if not oneOrMore: # pragma: no cover
                oneOrMore = []

            states_to_sum = zeroOrMore + oneOrMore

            total = sum([node_state_counts[i] for i in states_to_sum])
            has_minimum = sum([node_state_counts[i] for i in oneOrMore]) > 0

            return has_minimum and (total == node_count)

        if node_count == 0 and error_count == 0:
            return constants.EMPTY
        elif node_state_counts[constants.NORMAL] == node_count and error_count == 0:
            return constants.STABLE
        elif node_state_counts[constants.NORMAL] == node_count:
            return constants.STABLE_WITH_ERRORS
        elif state_check(oneOrMore=[constants.NORMAL, constants.WAITING_TO_JOIN]):
            return constants.JOIN_PENDING
        elif state_check(oneOrMore=[constants.NORMAL, constants.JOINING],
                         zeroOrMore=[constants.NORMAL_ACKNOWLEDGED_CHANGE,
                                     constants.JOINING_ACKNOWLEDGED_CHANGE]):
            return constants.STARTED_JOINING
        elif state_check(oneOrMore=[constants.NORMAL_ACKNOWLEDGED_CHANGE,
                                    constants.JOINING_ACKNOWLEDGED_CHANGE],
                         zeroOrMore=[constants.NORMAL_CONFIG_CHANGED,
                                     constants.JOINING_CONFIG_CHANGED]):
            return constants.JOINING_CONFIG_CHANGING
        elif state_check(oneOrMore=[constants.NORMAL_CONFIG_CHANGED,
                                    constants.JOINING_CONFIG_CHANGED],
                         zeroOrMore=[constants.NORMAL]):
            return constants.JOINING_RESYNCING
        elif state_check(oneOrMore=[constants.NORMAL, constants.WAITING_TO_LEAVE]):
            return constants.LEAVE_PENDING
        elif state_check(oneOrMore=[constants.NORMAL, constants.LEAVING],
                         zeroOrMore=[constants.NORMAL_ACKNOWLEDGED_CHANGE,
                                     constants.LEAVING_ACKNOWLEDGED_CHANGE]):
            return constants.STARTED_LEAVING
        elif state_check(oneOrMore=[constants.NORMAL_ACKNOWLEDGED_CHANGE,
                                    constants.LEAVING_ACKNOWLEDGED_CHANGE],
                         zeroOrMore=[constants.NORMAL_CONFIG_CHANGED,
                                     constants.LEAVING_CONFIG_CHANGED]):
            return constants.LEAVING_CONFIG_CHANGING
        elif state_check(oneOrMore=[constants.NORMAL_CONFIG_CHANGED,
                                    constants.LEAVING_CONFIG_CHANGED],
                         zeroOrMore=[constants.NORMAL, constants.FINISHED]):
            return constants.LEAVING_RESYNCING
        elif state_check(oneOrMore=[constants.NORMAL, constants.FINISHED]):
            return constants.FINISHED_LEAVING
        else: # pragma: no cover
            # Cluster in unexpected state.
            return constants.INVALID_CLUSTER_STATE

    # Returns the local node's state in the cluster, and None if the local node
    # is not in the cluster.
    def local_state(self, ip):
        return self.view.get(ip)

