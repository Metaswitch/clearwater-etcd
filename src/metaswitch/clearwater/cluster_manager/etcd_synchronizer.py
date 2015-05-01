#!/usr/bin/python

import etcd
import json
from collections import defaultdict
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
        self._last_cluster_view = None
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
                _log.debug("Feeding %s, %s, %s into FSM" % (local_state,
                                                            cluster_state,
                                                            cluster_view))
                new_state = self._fsm.next(local_state,
                                           cluster_state,
                                           cluster_view)

            # If we have a new state, try and write it to etcd.
            if new_state:
                self.write_to_etcd(cluster_view, new_state)
            else:
                _log.debug("No state change")

    # This node has been asked to leave the cluster. Check if the cluster is in
    # a stable state, in which case we can leave. Otherwise, set a flag and
    # leave at the next available opportunity.
    def leave_cluster(self):
        cluster_view = {}
        result = self._client.get(self._key)
        try:
            cluster_view = json.loads(result.value)
        except:
            cluster_view = {}

        cluster_state = self.calculate_cluster_state(cluster_view)

        if cluster_state == STABLE:
            updated_cluster_view = self.update_cluster_view(cluster_view,
                                                            WAITING_TO_LEAVE)
            self.write_to_etcd(cluster_view, WAITING_TO_LEAVE)
        else:
            self._leaving_flag = True

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
            if state is not ERROR:
                node_count += 1
            else:
                error_count += 1

        if node_count == 0 and error_count == 0:
            return EMPTY
        elif node_state_counts[NORMAL] == node_count and error_count == 0:
            return STABLE
        elif node_state_counts[NORMAL] == node_count:
            # All nodes in NORMAL state.
            return STABLE_WITH_ERRORS
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

    # Read the state of the cluster from etcd.
    def read_from_etcd(self):
        cluster_view = {}

        try:
            result = self._client.get(self._key)
            try:
                cluster_view = json.loads(result.value)
            except:
                cluster_view = {}

            # If the cluster view hasn't changed since we last saw it, then
            # wait for it to change before doing anything else.
            _log.info("Read cluster view {} from etcd, comparing to last cluster view {}".format(cluster_view, self._last_cluster_view))
            if cluster_view == self._last_cluster_view:
                while not self._terminate_flag:
                    try:
                        result = self._client.watch(self._key,
                                                    index=result.modifiedIndex+1,
                                                    timeout=5,
                                                    recursive=False)
                        break
                    except etcd.EtcdKeyError:
                        raise
                    except etcd.EtcdException:
                        pass
                    except urllib3.exceptions.TimeoutError:
                        pass
                    except ValueError:
                        # The index isn't valid to watch on, probably because
                        # there has been a snapshot between the get and the
                        # watch. Just start the read again.
                        _log.info("etcd index {} is invalid, retrying".format(result.modifiedIndex+1))
                        self._read_from_etcd()

                # Return if we're termiating.
                if self._terminate_flag:
                    return
                else:
                    try:
                        cluster_view = json.loads(result.value)
                    except:
                        cluster_view = {}

            # Save off the index of the result we're using for when we write
            # back to etcd later.
            self._index = result.modifiedIndex

        except etcd.EtcdKeyError:
            # If the key doesn't exist in etcd then there is currently no
            # cluster.
            self._index = None
            pass

        self._last_cluster_view = cluster_view.copy()
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
    def write_to_etcd(self, old_cluster_view, new_state, with_index=None):
        cluster_view = old_cluster_view.copy()
        if isinstance(new_state, str):
            cluster_view[self._ip] = new_state
        elif isinstance(new_state, dict):
            cluster_view = new_state
        _log.debug("Writing state %s into etcd" %
                    (cluster_view))
        json_data = json.dumps(cluster_view)

        try:
            if with_index:
                self._client.write(self._key, json_data, prevIndex=with_index)
            if self._index is None:
                self._client.write(self._key, json_data, prevExist=False)
            else:
                self._client.write(self._key, json_data, prevIndex=self._index)

                # We may have just successfully set the local node to
                # WAITING_TO_LEAVE, in which case we no longer need the leaving
                # flag.
                self._leaving_flag = False
        except ValueError:
            _log.debug("Contention on etcd write")
            if isinstance(new_state, str):
                result = self._client.get(self._key)
                cluster_view = json.loads(result.value)
                if (cluster_view[self._ip] == old_cluster_view[self._ip] and
                    cluster_view != old_cluster_view and
                    (self.calculate_cluster_state(cluster_view) ==
                     self.calculate_cluster_state(old_cluster_view))):
                    self.write_to_etcd(cluster_view, new_state, with_index=result.modifiedIndex)
