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

def id_in_queue(node_id, queue):
    for val in queue:
        if val[constants.JSON_ID] == node_id:
            return True
    return False

def status_in_queue(queue, node_id):
    status = []
    for val in queue:
        if val[constants.JSON_ID] == node_id:
            status.append(val[constants.JSON_STATUS])
    return status

def add_id_to_json(queue, node_id, status):
    add = {}
    add[constants.JSON_ID] = node_id
    add[constants.JSON_STATUS] = status
    queue.append(add)

def remove_id_from_json(node_id, queue):
    remaining = []
    for val in queue:
        if val[constants.JSON_ID] != node_id:
            remaining.append(val)
    return remaining

def move_to_processing(queue_func, node_id):
    queue = queue_func()
    queue[constants.JSON_QUEUED][0][constants.JSON_STATUS] = constants.S_PROCESSING
    remove_id_from_json(node_id, queue[constants.JSON_ERRORED])

def mark_node_as_errored(queue, node_id):
    del queue[constants.JSON_QUEUED][0]

    if not (len(queue[constants.JSON_QUEUED]) > 0 and \
            queue[constants.JSON_QUEUED][0][constants.JSON_ID] == node_id):
        add_id_to_json(queue[constants.JSON_ERRORED], node_id, constants.S_UNRESPONSIVE)
