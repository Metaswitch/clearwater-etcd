#!/usr/bin/python

import etcd
import json
from collections import defaultdict
from threading import Thread

from .constants import *
from .synchronization_fsm import SyncFSM


class EtcdSynchronizer(object):

    def __init__(self, plugin, ip):
        self._fsm = SyncFSM(plugin, ip)
        self._ip = ip
        self._client = etcd.Client(ip, 4000)
        self._key = plugin._key
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
            cluster_view = self.read_from_etcd()
            if self._terminate_flag:
                return
            cluster_state = self.calculate_cluster_state(cluster_view)

            # This node can only leave the cluster if the cluster is in a stable
            # state. Check the leaving flag and the cluster state. If necessary,
            # set this node to WAITING_TO_LEAVE. Otherwise, kick the FSM.
            if self._leaving_flag and cluster_state == STABLE:
                new_state = WAITING_TO_LEAVE
            else:
                local_state = self.calculate_local_state(cluster_view)
                new_state = self._fsm.next(local_state,
                                           cluster_state,
                                           cluster_view)

            # If we have a new state, try and write it to etcd.
            if new_state:
                updated_cluster_view = self.update_cluster_view(cluster_view,
                                                                new_state)
                self.write_to_etcd(updated_cluster_view)

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
        # Create a default dictionary. The default value of any key is 0.
        node_state_counts = defaultdict(int)
        node_states = cluster_view.values()
        node_count = 0

        # Count the number of nodes in each state. This will make working out
        # the state of the cluster below easier.
        for state in node_states:
            node_state_counts[state] += 1

            # Count the total number of nodes in the cluster. Ignore nodes in
            # ERROR state.
            if state is not ERROR:
                node_count += 1

        if node_state_counts[NORMAL] == node_count:
            # All nodes in NORMAL state.
            return STABLE
        elif (node_state_counts[NORMAL] +
              node_state_counts[WAITING_TO_JOIN] == node_count):
            # All nodes in NORMAL or WAITING_TO_JOIN state.
            return JOIN_PENDING
        elif ((node_state_counts[JOINING] +
               node_state_counts[JOINING_ACKNOWLEDGED_CHANGE] +
               node_state_counts[NORMAL_ACKNOWLEDGED_CHANGE] +
               node_state_counts[NORMAL] == node_count) and
              (node_state_counts[JOINING] > 0 or
               node_state_counts[NORMAL] > 0)):
            # At least one node in either JOINING or NORMAL state, all other
            # nodes in JOINING_ACKNOWLEDGED_CHANGE or NORMAL_ACKNOWLEDGED_CHANGE
            # state.
            return STARTED_JOINING
        elif ((node_state_counts[JOINING_ACKNOWLEDGED_CHANGE] +
               node_state_counts[NORMAL_ACKNOWLEDGED_CHANGE] +
               node_state_counts[JOINING_CONFIG_CHANGED] +
               node_state_counts[NORMAL_CONFIG_CHANGED] == node_count) and
              (node_state_counts[JOINING_ACKNOWLEDGED_CHANGE] > 0 or
               node_state_counts[NORMAL_ACKNOWLEDGED_CHANGE] > 0)):
            # At least one node in either JOINING_ACKNOWLEDGED_CHANGE or
            # NORMAL_ACKNOWLEDGED_CHANGE state, all other nodes in
            # JOINING_CONFIG_CHANGED or NORMAL_CONFIG_CHANGED
            # state.
            return JOINING_CONFIG_CHANGING
        elif (node_state_counts[JOINING_CONFIG_CHANGED] +
              node_state_counts[NORMAL_CONFIG_CHANGED] +
              node_state_counts[NORMAL] == node_count):
            # All nodes in JOINING_CONFIG_CHANGED, NORMAL_CONFIG_CHANGED or
            # NORMAL state.
            return JOINING_RESYNCING
        elif (node_state_counts[NORMAL] +
              node_state_counts[WAITING_TO_LEAVE] == node_count):
            # All nodes in NORMAL or WAITING_TO_LEAVE state.
            return LEAVE_PENDING
        elif ((node_state_counts[LEAVING] +
               node_state_counts[LEAVING_ACKNOWLEDGED_CHANGE] +
               node_state_counts[NORMAL_ACKNOWLEDGED_CHANGE] +
               node_state_counts[NORMAL] == node_count) and
              (node_state_counts[LEAVING] > 0 or
               node_state_counts[NORMAL] > 0)):
            # At least one node in either LEAVING or NORMAL state, all other
            # nodes in LEAVING_ACKNOWLEDGED_CHANGE or NORMAL_ACKNOWLEDGED_CHANGE
            # state.
            return STARTED_LEAVING
        elif ((node_state_counts[LEAVING_ACKNOWLEDGED_CHANGE] +
               node_state_counts[NORMAL_ACKNOWLEDGED_CHANGE] +
               node_state_counts[LEAVING_CONFIG_CHANGED] +
               node_state_counts[NORMAL_CONFIG_CHANGED] == node_count) and
              (node_state_counts[LEAVING_ACKNOWLEDGED_CHANGE] > 0 or
               node_state_counts[NORMAL_ACKNOWLEDGED_CHANGE] > 0)):
            # At least one node in either LEAVING_ACKNOWLEDGED_CHANGE or
            # NORMAL_ACKNOWLEDGED_CHANGE state, all other nodes in
            # LEAVING_CONFIG_CHANGED or NORMAL_CONFIG_CHANGED
            # state.
            return LEAVING_CONFIG_CHANGING
        elif ((node_state_counts[LEAVING_CONFIG_CHANGED] +
               node_state_counts[NORMAL_CONFIG_CHANGED] +
               node_state_counts[NORMAL] +
               node_state_counts[FINISHED] == node_count) and
              (node_state_counts[LEAVING_CONFIG_CHANGED] > 0 or
               node_state_counts[NORMAL_CONFIG_CHANGED] > 0)):
            # All nodes in LEAVING_CONFIG_CHANGED,
            # NORMAL_CONFIG_CHANGED, FINISHED or NORMAL state.
            return LEAVING_RESYNCING
        elif (node_state_counts[NORMAL] +
              node_state_counts[FINISHED] == node_count):
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
                                                    index=self._index+1,
                                                    timeout=0.1)
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
