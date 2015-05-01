#!/usr/bin/python

import etcd
import json
from threading import Thread

from .constants import *
from .synchronization_fsm import SyncFSM
import urllib3
import logging

_log = logging.getLogger("etcd_sync")


class EtcdSynchronizer(object):

    def __init__(self, plugin, ip):
        self._fsm = SyncFSM(plugin, ip)
        self._ip = ip
        self._client = etcd.Client(ip, 4000)
        self._key = plugin.key()
        self._index = None
        self._leaving_flag = False
        self._terminate_flag = False
        self.thread = Thread(target=self.main)

    def start_thread(self):
        self.thread.daemon = True
        self.thread.start()

    def terminate(self):
        self._terminate_flag = True
        self.thread.join()
        self._fsm.quit()

    def main(self):
        # Continue looping while the FSM is running.
        while self._fsm.is_running():
            # This blocks on changes to the cluster in etcd.
            _log.debug("Waiting for state change from etcd")
            cluster_view = self.read_from_etcd()
            if self._terminate_flag:
                return
            _log.debug("Got new state %s from etcd" % cluster_view)
            cluster_state = self.calculate_cluster_state(cluster_view)

            # This node can only leave the cluster if the cluster is in a stable
            # state. Check the leaving flag and the cluster state. If necessary,
            # set this node to WAITING_TO_LEAVE. Otherwise, kick the FSM.
            if self._leaving_flag and cluster_state == STABLE:
                new_state = WAITING_TO_LEAVE
            else:
                local_state = self.calculate_local_state(cluster_view)
                _log.debug("Feeding %s, %s, %s into FSM" % (local_state, cluster_state, cluster_view))
                new_state = self._fsm.next(local_state,
                                           cluster_state,
                                           cluster_view)

            # If we have a new state, try and write it to etcd.
            if new_state:
                updated_cluster_view = self.update_cluster_view(cluster_view,
                                                                new_state)
                _log.debug("Writing state %s into etcd" % (updated_cluster_view))
                self.write_to_etcd(updated_cluster_view)
            else:
                _log.debug("No state change")

    # This node has been asked to leave the cluster. Check if the cluster is in
    # a stable state, in which case we can leave. Otherwise, set a flag and
    # leave at the next available opportunity.
    def leave_cluster(self):
        cluster_view = self.read_from_etcd()
        cluster_state = self.calculate_cluster_state(cluster_view)

        if cluster_state == STABLE:
            updated_cluster_view = self.update_cluster_view(cluster_view,
                                                            WAITING_TO_LEAVE)
            self.write_to_etcd(updated_cluster_view)
        else:
            self._leaving_flag = True

    # Calculate the state of the cluster based on the state of all the nodes in
    # the cluster.
    def calculate_cluster_state(self, cluster_view):
        node_states = cluster_view.values()

        if all(state == NORMAL for state in node_states):
            # All nodes in NORMAL state.
            return STABLE
        elif all((state == NORMAL or
                  state == WAITING_TO_JOIN) for state in node_states):
            # All nodes in NORMAL or WAITING_TO_JOIN state.
            return JOIN_PENDING
        elif (all((state == JOINING or
                  state == JOINING_ACKNOWLEDGED_CHANGE or
                  state == NORMAL_ACKNOWLEDGED_CHANGE or
                  state == NORMAL) for state in node_states) and
              (JOINING in node_states or
               NORMAL in node_states)):
            # All nodes in JOINING, JOINING_ACKNOWLEDGED_CHANGE
            # NORMAL_ACKNOWLEDGED_CHANGE or NORMAL state.
            return STARTED_JOINING
        elif (all((state == JOINING_ACKNOWLEDGED_CHANGE or
                   state == NORMAL_ACKNOWLEDGED_CHANGE or
                   state == JOINING_CONFIG_CHANGED or
                   state == NORMAL_CONFIG_CHANGED)
                  for state in node_states) and
              (JOINING_ACKNOWLEDGED_CHANGE in node_states or
               NORMAL_ACKNOWLEDGED_CHANGE in node_states)):
            # At least one node in either JOINING_ACKNOWLEDGED_CHANGE or
            # NORMAL_ACKNOWLEDGED_CHANGE, all other nodes in
            # JOINING_CONFIG_CHANGED or NORMAL_CONFIG_CHANGED
            # state.
            return JOINING_CONFIG_CHANGING
        elif all((state == JOINING_CONFIG_CHANGED or
                  state == NORMAL_CONFIG_CHANGED or
                  state == NORMAL) for state in node_states):
            # All nodes in JOINING_CONFIG_CHANGED,
            # NORMAL_CONFIG_CHANGED or NORMAL state.
            return JOINING_RESYNCING
        elif all((state == NORMAL or
                  state == WAITING_TO_LEAVE) for state in node_states):
            # All nodes in NORMAL or WAITING_TO_LEAVE state.
            return LEAVE_PENDING
        elif (all((state == LEAVING or
                  state == LEAVING_ACKNOWLEDGED_CHANGE or
                  state == NORMAL_ACKNOWLEDGED_CHANGE or
                  state == NORMAL) for state in node_states) and
              (LEAVING in node_states or
               NORMAL in node_states)):
            # All nodes in LEAVING, LEAVING_ACKNOWLEDGED_CHANGE
            # NORMAL_ACKNOWLEDGED_CHANGE or NORMAL state.
            return STARTED_LEAVING
        elif (all((state == LEAVING_ACKNOWLEDGED_CHANGE or
                   state == NORMAL_ACKNOWLEDGED_CHANGE or
                   state == LEAVING_CONFIG_CHANGED or
                   state == NORMAL_CONFIG_CHANGED)
                  for state in node_states) and
              (LEAVING_ACKNOWLEDGED_CHANGE in node_states or
               NORMAL_ACKNOWLEDGED_CHANGE in node_states)):
            # At least one node in either LEAVING_ACKNOWLEDGED_CHANGE or
            # NORMAL_ACKNOWLEDGED_CHANGE, all other nodes in
            # LEAVING_CONFIG_CHANGED or NORMAL_CONFIG_CHANGED
            # state.
            return LEAVING_CONFIG_CHANGING
        elif (all((state == LEAVING_CONFIG_CHANGED or
                  state == NORMAL_CONFIG_CHANGED or
                  state == FINISHED or
                  state == NORMAL) for state in node_states) and
              (LEAVING_CONFIG_CHANGED in node_states or
               NORMAL_CONFIG_CHANGED in node_states)):
            # All nodes in LEAVING_CONFIG_CHANGED,
            # NORMAL_CONFIG_CHANGED, FINISHED or NORMAL state.
            return LEAVING_RESYNCING
        elif all((state == NORMAL or
                  state == FINISHED) for state in node_states):
            # All nodes in NORMAL or FINISHED state.
            return FINISHED_LEAVING
        else:
            # Cluster in unexpected state.
            return INVALID_CLUSTER_STATE

    # Returns the local node's state in the cluster, and None if the local node
    # is not in the cluster.
    def calculate_local_state(self, cluster_view):
        return cluster_view.get(self._ip)

    # Read the state of the cluster from etcd. The first time we do this, we get
    # the current state. On subsequent calls we get the most recent state of the
    # cluster that we haven't previously seen. This may mean waiting for a
    # change.
    def read_from_etcd(self):
        cluster_view = {}
        try:
            if self._index is None:
                result = self._client.get(self._key)
            else:
                while not self._terminate_flag:
                    try:
                        result = self._client.watch(self._key,
                                                     index=self._index,
                                                     timeout=5)
                        break
                    except urllib3.exceptions.TimeoutError:
                        pass
            if self._terminate_flag:
                return
            cluster_view = json.loads(result.value)
            self._index = result.modifiedIndex
        except etcd.EtcdKeyError:
            # If the key doesn't exist in etcd then there is currently no
            # cluster.
            self._index = None

        return cluster_view

    # Update the cluster view based on new state information. If new_state is a
    # string then it refers to the new state of the local node. Otherwise, it is
    # an overall picture of the new cluster.
    def update_cluster_view(self, cluster_view, new_state):
        if isinstance(new_state, str):
            cluster_view[self._ip] = new_state
        elif isinstance(new_state, dict):
            cluster_view = new_state

        return cluster_view

    # Write the new cluster view to etcd. We may be expecting to create the key
    # for the first time.
    def write_to_etcd(self, cluster_view):
        json_data = json.dumps(cluster_view)

        try:
            if self._index is None:
                self._client.write(self._key, json_data, prevExist=False)
            else:
                self._client.write(self._key, json_data, prevIndex=self._index)

                # We may have just successfully set the local node to
                # WAITING_TO_LEAVE, in which case we no longer need the leaving
                # flag.
                self._leaving_flag = False
        except ValueError:
            pass
