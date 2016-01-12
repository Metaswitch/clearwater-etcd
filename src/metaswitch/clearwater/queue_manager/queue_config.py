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

import constants
import logging

_log = logging.getLogger(__name__)

# This class represents the queue configuration stored in etcd.
class QueueConfig(object):
    def __init__(self, node_id, value):
        self._node_id = node_id
        self._value = value

    # Return the queue configuration (as a dictionary)
    def get_value(self):
        return self._value

    # Return the node ID at the front of the queue
    def node_at_the_front_of_the_queue(self):
        if not self._is_json_list_empty(constants.JSON_QUEUED):
            return self._value[constants.JSON_QUEUED][0][constants.JSON_ID]
        else:
            return "NONE - queue empty"

    # Calculate the local state of the node
    def calculate_local_state(self):
        if self._is_json_list_empty(constants.JSON_QUEUED):
            # If the queue is empty, then the node can either be in the
            # NO_QUEUE or NO_QUEUE_ERROR state
            if self._node_in_json_list(self._node_id, constants.JSON_ERRORED):
                return constants.LS_NO_QUEUE_ERROR
            else:
                return constants.LS_NO_QUEUE
        else:
            # There is a queue, check whether we're at the front.
            if self.node_at_the_front_of_the_queue() == self._node_id:
                if self._value[constants.JSON_QUEUED][0][constants.JSON_STATUS] == \
                   constants.S_QUEUED:
                    return constants.LS_FIRST_IN_QUEUE
                else:
                    return constants.LS_PROCESSING
            else:
                # We're not at the front of the queue, so check whether we're
                # errored or not to determine the local state.
                if self._node_in_json_list(self._node_id, constants.JSON_ERRORED):
                    return constants.LS_WAITING_ON_OTHER_NODE_ERROR
                else:
                    return constants.LS_WAITING_ON_OTHER_NODE

    # Calculate the global state of the deployment
    def calculate_global_state(self):
        if self._is_json_list_empty(constants.JSON_QUEUED):
            if self._is_json_list_empty(constants.JSON_ERRORED):
                return constants.GS_NO_SYNC
            else:
                return constants.GS_NO_SYNC_ERROR
        else:
            if self._is_json_list_empty(constants.JSON_ERRORED):
                return constants.GS_SYNC
            else:
                return constants.GS_SYNC_ERROR

    # Update the FORCE value in the queue configuration
    def set_force(self, force):
        self._value[constants.JSON_FORCE] = force

    # Add the node to the QUEUE list
    def add_to_queue(self, node_id):
        # If the QUEUE is empty, first copy any errored nodes to the front of
        # the queue
        if self._is_json_list_empty(constants.JSON_QUEUED):
            self._copy_failed_nodes_to_queue()
            self._empty_json_list(constants.JSON_ERRORED)

        self._add_node_to_json_list(node_id, constants.JSON_QUEUED, constants.S_QUEUED)
        self._remove_node_from_json_list(node_id, constants.JSON_COMPLETED)

    # Move a node from QUEUED to PROCESSING
    def move_to_processing(self):
        if self.node_at_the_front_of_the_queue() == self._node_id:
            self._value[constants.JSON_QUEUED][0][constants.JSON_STATUS] = constants.S_PROCESSING

    # Mark a node as unresponsive
    def mark_node_as_unresponsive(self, node_id):
        self._remove_first_entry_from_queue()
        self._node_failure_processing(node_id, constants.S_UNRESPONSIVE)
        self._remove_node_from_json_list(self.node_at_the_front_of_the_queue(), constants.JSON_ERRORED)

    # Remove a node from the queue 
    def remove_from_queue(self, successful, node_id):
        if self._node_is_being_processed(node_id):
            self._remove_first_entry_from_queue()

            if successful:
                if not self._node_in_json_list(node_id, constants.JSON_QUEUED) and \
                    not self._is_json_list_empty(constants.JSON_QUEUED):
                    self._add_node_to_json_list(node_id, constants.JSON_COMPLETED, constants.S_DONE)
            else:
                self._node_failure_processing(node_id, constants.S_FAILURE)

            self._remove_node_from_json_list(self.node_at_the_front_of_the_queue(), constants.JSON_ERRORED)

    # Deal with an errored node. We may stop the resync if FORCE is false
    def _node_failure_processing(self, node_id, status):
        # We only keep going if FORCE is true
        if self._value[constants.JSON_FORCE]:
            if not self.node_at_the_front_of_the_queue() == node_id:
                # When a node is about to be retried, we don't mark it as being
                # in the errored state (to be consistent with the case when a
                # resync stops fully and is then retried).
                self._add_node_to_json_list(node_id, constants.JSON_ERRORED, status)
        else:
            self._add_node_to_json_list(node_id, constants.JSON_ERRORED, status)
            self._empty_json_list(constants.JSON_QUEUED)
            self._empty_json_list(constants.JSON_COMPLETED)

    # Remove the first entry from the QUEUE list. Empty the completed list
    # if this means that the QUEUE is now empty.
    def _remove_first_entry_from_queue(self):
        del self._value[constants.JSON_QUEUED][0]
        if self._is_json_list_empty(constants.JSON_QUEUED):
            self._empty_json_list(constants.JSON_COMPLETED)

    # Check if the json list is empty
    def _is_json_list_empty(self, list_to_check):
        return len(self._value[list_to_check]) == 0

    # Check if a node id is in a json list
    def _node_in_json_list(self, node_id, list_to_check):
        for entry in self._value[list_to_check]:
            if entry[constants.JSON_ID] == node_id:
                return True
        return False

    # Clear a json list
    def _empty_json_list(self, json_list_to_empty):
        self._value[json_list_to_empty][:] = []

    # Get the statuses of a node in a json list. There can be
    # multiple statuses of a node in the QUEUED list.
    def _node_statuses_in_json_list(self, node_id, list_to_check):
        statuses = []

        for val in self._value[list_to_check]:
            if val[constants.JSON_ID] == node_id:
                statuses.append(val[constants.JSON_STATUS])

        return statuses

    # Copy any failed nodes from the ERRORED list to the QUEUE list
    def _copy_failed_nodes_to_queue(self):
        for node in self._value[constants.JSON_ERRORED]:
            if node[constants.JSON_STATUS] == constants.S_FAILURE:
                self._add_node_to_json_list(node[constants.JSON_ID], constants.JSON_QUEUED, constants.S_QUEUED)

    # Add a node+status to a json list. If the node+status already exists then
    # there's no change
    def _add_node_to_json_list(self, node_id, json_list, status):
        if status not in self._node_statuses_in_json_list(node_id, json_list):
            add = {}
            add[constants.JSON_ID] = node_id
            add[constants.JSON_STATUS] = status
            self._value[json_list].append(add)

    # Remove all entries of a node from a JSON list. If it doesn't exist
    # in the list then there's no change
    def _remove_node_from_json_list(self, node_id, json_list):
        remaining = []

        for node in self._value[json_list]:
            if node[constants.JSON_ID] != node_id:
                remaining.append(node)

        self._value[json_list] = remaining

    # Return whether a node is at the front of the queue and in the PROCESSING state 
    def _node_is_being_processed(self, node_id):
        return ((self.node_at_the_front_of_the_queue() == node_id) and \
                (self._value[constants.JSON_QUEUED][0][constants.JSON_STATUS] == constants.S_PROCESSING))
