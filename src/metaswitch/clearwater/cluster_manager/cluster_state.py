#!/usr/bin/python

# Copyright (C) Metaswitch Networks 2015
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

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
        except: # pragma : no cover
            pass

        self.cluster_state = self.calculate_cluster_state(self.view)


    def can_leave(self, force_leave=False):
        return self.cluster_state == constants.STABLE or \
               self.cluster_state == constants.LEAVE_PENDING or \
                (force_leave and
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
        else:
            # Cluster in unexpected state.
            return constants.INVALID_CLUSTER_STATE

    # Returns the local node's state in the cluster, and None if the local node
    # is not in the cluster.
    def local_state(self, ip):
        return self.view.get(ip)

