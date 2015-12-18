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
from queue_utils import id_in_queue

_log = logging.getLogger(__name__)

class QueueStateInfo(object):
    def __init__(self, node_id, value):
        self._node_id = node_id
        self._view = value
        self.global_state = self._calculate_global_state()
        self.local_state = self._calculate_local_state()
        _log.debug("Global state is %s" % self.global_state)
        _log.debug("Local state is %s" % self.local_state)
       
    def current_node_id(self):
        if len(self._view[constants.JSON_QUEUED]) != 0:
            return self._view[constants.JSON_QUEUED][0][constants.JSON_ID]
        else:
            return ""

    def _calculate_local_state(self):
        if len(self._view[constants.JSON_QUEUED]) == 0:
            if id_in_queue(self._node_id, self._view[constants.JSON_ERRORED]):
                return constants.LS_NO_QUEUE_ERROR
            else:
                return constants.LS_NO_QUEUE
        else:
            if self._view[constants.JSON_QUEUED][0][constants.JSON_ID] == self._node_id:
                if self._view[constants.JSON_QUEUED][0][constants.JSON_STATUS] == constants.S_QUEUED:
                    return constants.LS_FIRST_IN_QUEUE
                else:
                    return constants.LS_PROCESSING
            else:
                if id_in_queue(self._node_id, self._view[constants.JSON_ERRORED]):
                    return constants.LS_WAITING_ON_OTHER_NODE_ERROR
                else:
                    return constants.LS_WAITING_ON_OTHER_NODE

    def _calculate_global_state(self):
        if len(self._view[constants.JSON_QUEUED]) == 0:
            if len(self._view[constants.JSON_ERRORED]) == 0:
                return constants.GS_NO_SYNC
            else:
                return constants.GS_NO_SYNC_ERROR
        else:
            if len(self._view[constants.JSON_ERRORED]) == 0:
                return constants.GS_SYNC
            else:
                return constants.GS_SYNC_ERROR
