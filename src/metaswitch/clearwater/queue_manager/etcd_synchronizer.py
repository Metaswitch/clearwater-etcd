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
import constants
from time import sleep
from concurrent import futures
from metaswitch.clearwater.etcd_shared.common_etcd_synchronizer import CommonEtcdSynchronizer
from .queue_fsm import QueueFSM
import logging
from etcd import EtcdAlreadyExist
from queue_utils import remove_id_from_json, add_id_to_json, status_in_queue

_log = logging.getLogger(__name__)

class EtcdSynchronizer(CommonEtcdSynchronizer):
    def __init__(self, plugin, ip, site, key, node_type, etcd_ip=None):
        super(EtcdSynchronizer, self).__init__(plugin, ip, etcd_ip)
        self.WAIT_FOR_TIMER_POP = 1
        self._id = ip + "-" + node_type
        self._timer_flag = False
        self._fsm = QueueFSM(self._plugin, self._id, self.fsm_timer_expired)
        self._site = site
        self._key = key

    def key(self):
        return "/" + self._key + "/" + self._site + "/configuration/" + self._plugin.key()

    def is_running(self):
        return self._fsm.is_running()

    def default_value(self):
        return "{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": []}"
 
    def main(self):
        # Continue looping while the FSM is running.
        while self._fsm.is_running():
            _log.debug("Waiting for queue change from etcd")

            etcd_result = None
            self._abort_read = False

            executor = futures.ThreadPoolExecutor(2)
            fsm_timer_future = executor.submit(self.wait_for_fsm)
            etcd_future = executor.submit(self.update_from_etcd)
            futures.wait([etcd_future, fsm_timer_future], return_when=futures.FIRST_COMPLETED)

            if self._terminate_flag:
                executor.shutdown(wait=False)    
                break

            if fsm_timer_future.done():
                self._timer_flag = False
                self.fsm_loop()
                self._abort_read = True

            elif etcd_future.done():
                etcd_result = etcd_future.result()

                if etcd_result is not None:
                    _log.info("Got new queue config %s from etcd" % etcd_result)
                    self.fsm_loop(etcd_result)
                else: #pragma: no cover
                    _log.warning("read_from_etcd returned None, " +
                                 "indicating a failure to get data from etcd")
                # ensure the other thread ends
                self._timer_flag = True 
                
            executor.shutdown()    

        _log.info("Quitting FSM")
        self._fsm.quit()

    def fsm_timer_expired(self):
        self._timer_flag = True;

    def wait_for_fsm(self):
        while not self._timer_flag and not self._terminate_flag:
            sleep(self.WAIT_FOR_TIMER_POP)

    def fsm_loop(self, etcd_value=None): # Change to add helper message
        queue_config = {}

        try:
            if etcd_value is None:
                if self._last_value is None: # pragma: no cover
                    queue_config = json.loads(self.default_value())
                else:
                    queue_config = json.loads(self._last_value)
            else:
                queue_config = json.loads(etcd_value)
        except: # pragma: no cover
            queue_config = json.loads(self.default_value())

        self._fsm.fsm_update(queue_config)
        etcd_updated_value = json.dumps(queue_config)

        # If we have a new state, try and write it to etcd.
        if etcd_updated_value != self._last_value:
            _log.debug("Writing updated queue config to etcd")

            if not self.write_to_etcd(etcd_updated_value):
                self.fsm_loop(etcd_updated_value)

    # Write the new cluster view to etcd. We may be expecting to create the key
    # for the first time.
    def write_to_etcd(self, queue_config):
        _log.debug("Writing state {} into etcd with index {}"
                   .format(queue_config, self._index))
        needs_no_retry = True

        try:
            if self._index:
                self._client.write(self.key(), queue_config, prevIndex=self._index)
            else: # pragma: no cover
                self._client.write(self.key(), queue_config, prevExist=False)
        except (EtcdAlreadyExist, ValueError): # pragma: no cover
            _log.debug("Contention on etcd write")
            # Our etcd write failed because someone got there before us. We
            # don't need to retry in this case as we'll just pick up the
            # changes in the next etcd read
        except Exception as e:
            # Catch-all error handler (for invalid requests, timeouts, etc) -
            # unset our state and start over.
            _log.error("{} caught {!r} when trying to write {} with index {}"
                       " - pause before retrying"
                       .format(self._ip, e, queue_config, self._index))

            # Setting last_cluster_view to None means that the next successful
            # read from etcd will trigger the state machine, which will mean
            # that any necessary work/state changes get retried.
            self._last_value, self._last_index = None, None

            # Sleep briefly to avoid hammering a failed server
            self.pause()
            needs_no_retry = False
     
        return needs_no_retry

    def remove_from_queue(self, successful):
        # Get and parse the current value
        self._last_value, self._index = self.read_from_etcd(wait=False)
        queue_config = json.loads(self._last_value)

        # What is the current status?
        queue_status = status_in_queue(queue_config[constants.JSON_QUEUED], self._id)
        restart_status = status_in_queue(queue_config[constants.JSON_COMPLETED], self._id)
        error_status = status_in_queue(queue_config[constants.JSON_ERRORED], self._id)

        if len(queue_config[constants.JSON_QUEUED]) > 0 and \
           queue_config[constants.JSON_QUEUED][0][constants.JSON_ID] == self._id and \
           queue_config[constants.JSON_QUEUED][0][constants.JSON_STATUS] == constants.S_PROCESSING:
            del queue_config[constants.JSON_QUEUED][0]
            
            if successful:
                if constants.S_QUEUED not in queue_status and restart_status == []:
                    add_id_to_json(queue_config[constants.JSON_COMPLETED], self._id, constants.S_DONE)
            else:
                if not (len(queue_config[constants.JSON_QUEUED]) > 0 and \
                        queue_config[constants.JSON_QUEUED][0][constants.JSON_ID] == self._id) and \
                   constants.S_FAILURE not in error_status:
                    remove_id_from_json(self._id, queue_config[constants.JSON_ERRORED])
                    add_id_to_json(queue_config[constants.JSON_ERRORED], self._id, constants.S_FAILURE)
 
            if len(queue_config[constants.JSON_QUEUED]) > 0 and \
               status_in_queue(queue_config[constants.JSON_ERRORED], queue_config[constants.JSON_QUEUED][0][constants.JSON_ID]) != []:
                remove_id_from_json(queue_config[constants.JSON_QUEUED][0][constants.JSON_ID], queue_config[constants.JSON_ERRORED])

        return self.write_to_etcd(json.dumps(queue_config))

    def add_to_queue(self):
        # Get and parse the current value
        self._last_value, self._index = self.read_from_etcd(wait=False)
        queue_config = json.loads(self._last_value)

        # What is our current status?
        queue_status = status_in_queue(queue_config[constants.JSON_QUEUED], self._id)
        restart_status = status_in_queue(queue_config[constants.JSON_COMPLETED], self._id)
        error_status = status_in_queue(queue_config[constants.JSON_ERRORED], self._id)

        if len(queue_config[constants.JSON_QUEUED]) == 0:
            # There are no queued nodes. Adding a new node in this case means that we want to
            for x in queue_config[constants.JSON_ERRORED]:
                if x[constants.JSON_STATUS] == constants.S_FAILURE:
                    add_id_to_json(queue_config[constants.JSON_QUEUED], x[constants.JSON_ID], constants.S_QUEUED)

            queue_config[constants.JSON_COMPLETED][:] = []
            queue_config[constants.JSON_ERRORED][:] = []

            if status_in_queue(queue_config[constants.JSON_QUEUED], self._id) == []:
                add_id_to_json(queue_config[constants.JSON_QUEUED], self._id, constants.S_QUEUED)
        elif queue_status == []:
            if restart_status != []:
                queue_config[constants.JSON_COMPLETED] = remove_id_from_json(self._id, queue_config[constants.JSON_COMPLETED])
            add_id_to_json(queue_config[constants.JSON_QUEUED], self._id, constants.S_QUEUED)
            
            if queue_config[constants.JSON_QUEUED][0][constants.JSON_ID] == self._id and \
               error_status != []:
                remove_id_from_json(self._id, queue_config[constants.JSON_ERRORED])
        elif constants.S_QUEUED in queue_status:
            if restart_status != []:
                # We're in both the restarted and queued lists. Remove ourselves from
                # the restarted list
                queue_config[constants.JSON_COMPLETED] = remove_id_from_json(self._id, queue_config[constants.JSON_COMPLETED])
        else:
            if restart_status != []:
                queue_config[constants.JSON_COMPLETED] = remove_id_from_json(self._id, queue_config[constants.JSON_COMPLETED])
            add_id_to_json(queue_config[constants.JSON_QUEUED], self._id, constants.S_QUEUED)

        return self.write_to_etcd(json.dumps(queue_config))

    def set_force(self, force):
        # Get and parse the current value
        etcd_result, idx = self.read_from_etcd(wait=False)
        queue_config = json.loads(etcd_result)
        queue_config[constants.JSON_FORCE] = force
        updated_etcd_result = json.dumps(queue_config)

        if updated_etcd_result != etcd_result:
            return self.write_to_etcd(json.dumps(queue_config))
        else:
            return True
