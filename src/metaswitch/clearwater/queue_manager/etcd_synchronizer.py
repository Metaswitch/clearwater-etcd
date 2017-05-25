#!/usr/bin/python

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import json
from time import sleep
from concurrent import futures
from metaswitch.clearwater.etcd_shared.common_etcd_synchronizer import CommonEtcdSynchronizer
from queue_fsm import QueueFSM
import logging
from etcd import EtcdAlreadyExist
from queue_config import QueueConfig

_log = logging.getLogger(__name__)

class WriteToEtcdStatus:
    SUCCESS = 0
    CONTENTION = 1
    ERROR = 2

class EtcdSynchronizer(CommonEtcdSynchronizer):
    def __init__(self, plugin, ip, site, key, node_type, etcd_ip=None):
        super(EtcdSynchronizer, self).__init__(plugin, ip, etcd_ip)
        self.WAIT_FOR_TIMER_POP = 1
        self._id = ip + "-" + node_type
        self._stop_timer_thread = False
        self._fsm = QueueFSM(self._plugin, self._id, self.fsm_timer_expired)
        self._site = site
        self._key = key

    def key(self):
        return "/" + self._key + "/" + self._site + "/configuration/" + self._plugin.key()

    def is_running(self):
        return self._fsm.is_running()

    def default_value(self): #pragma: no cover
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

            # At this point, the executor has returned. This is either
            # because the timer has popped, or etcd has detected a
            # change to the underlying key. We firstly check whether the
            # terminate flag has been set, and then check which future is
            # marked as done (making sure that the other thread terminates by
            # setting the appropriate flags for each future)
            if self._terminate_flag:
                executor.shutdown(wait=False)
                break

            if fsm_timer_future.done():
                self._abort_read = True
                self._stop_timer_thread = False
                self.fsm_loop()
            elif etcd_future.done():
                self._stop_timer_thread = True
                etcd_result = etcd_future.result()

                if etcd_result is not None:
                    _log.info("Got new queue config %s from etcd" % etcd_result)
                    self.fsm_loop(etcd_result)
                else: #pragma: no cover
                    _log.warning("read_from_etcd returned None, " +
                                 "indicating a failure to get data from etcd")

            executor.shutdown()

        _log.info("Quitting FSM")
        self._fsm.quit()

    def fsm_timer_expired(self):
        self._stop_timer_thread = True;

    def wait_for_fsm(self):
        while not self._stop_timer_thread and not self._terminate_flag:
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
        except Exception: # pragma: no cover
            queue_config = json.loads(self.default_value())

        self._fsm.fsm_update(queue_config)
        etcd_updated_value = json.dumps(queue_config)

        # If we have a new state, try and write it to etcd.
        if etcd_updated_value != self._last_value:
            _log.debug("Writing updated queue config to etcd")
            self.write_to_etcd(etcd_updated_value)

    # Write the new cluster view to etcd. We may be expecting to create the key
    # for the first time.
    def write_to_etcd(self, queue_config, with_index=None):
        index = with_index or self._index
        _log.info("Writing state {} into etcd with index {}"
                   .format(queue_config, self._index))
        rc = WriteToEtcdStatus.SUCCESS

        try:
            if index:
                self._client.write(self.key(), queue_config, prevIndex=index)
            else: # pragma: no cover
                self._client.write(self.key(), queue_config, prevExist=False)
        except (EtcdAlreadyExist, ValueError): # pragma: no cover
            _log.debug("Contention on etcd write")
            # Our etcd write failed because someone got there before us. We
            # don't need to retry in this case as we'll just pick up the
            # changes in the next etcd read
            self._last_value, self._last_index, self._fsm._last_local_state = None, None, None
            rc = WriteToEtcdStatus.CONTENTION
        except Exception as e: #pragma: no cover
            # Catch-all error handler (for invalid requests, timeouts, etc) -
            # unset our state and start over.
            _log.error("{} caught {!r} when trying to write {} with index {}"
                       " - pause before retrying"
                       .format(self._ip, e, queue_config, self._index))

            # Setting last_cluster_view to None means that the next successful
            # read from etcd will trigger the state machine, which will mean
            # that any necessary work/state changes get retried.
            # Sleep briefly to avoid hammering a failed server
            self._last_value, self._last_index, self._fsm._last_local_state = None, None, None
            self.pause()
            rc = WriteToEtcdStatus.ERROR

        return rc

    def edit_queue_config(self, function, *args, **kwargs):
        # Get and parse the current value
        etcd_result, idx = self.read_from_etcd(wait=False)
        if etcd_result is None: #pragma: no cover
            return WriteToEtcdStatus.ERROR

        queue_config = QueueConfig(self._id, json.loads(etcd_result))
        function(queue_config, *args, **kwargs)
        # If the JSON changed, write it back to etcd
        updated_etcd_result = json.dumps(queue_config.get_value())

        if updated_etcd_result != etcd_result:
            return self.write_to_etcd(updated_etcd_result, idx)
        else: #pragma: no cover
            return WriteToEtcdStatus.SUCCESS

    def set_force(self, force):
        # Use the force
        return self.edit_queue_config(QueueConfig.set_force, force)

    def add_to_queue(self, node_id=None):
        if node_id == None:
            node_id = self._id
        return self.edit_queue_config(QueueConfig.add_to_queue, node_id)

    def remove_from_queue(self, successful, node_id=None):
        if node_id == None:
            node_id = self._id
        return self.edit_queue_config(QueueConfig.remove_from_queue, successful, node_id)
