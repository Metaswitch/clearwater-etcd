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

import etcd
import json
from collections import defaultdict
from threading import Thread
from time import sleep
from concurrent import futures

from .constants import *
from .synchronization_fsm import SyncFSM
import urllib3
import logging

_log = logging.getLogger("cluster_manager.etcd_synchronizer")


class EtcdSynchronizer(object):
    PAUSE_BEFORE_RETRY = 30

    def __init__(self, plugin, ip, etcd_ip=None, force_leave=False):
        self._plugin = plugin
        self._fsm = SyncFSM(plugin, ip)
        self._ip = ip
        if etcd_ip:
            self._client = etcd.Client(etcd_ip, 4000)
        else:
            self._client = etcd.Client(ip, 4000)
        self._key = plugin.key()
        self._index = None
        self._last_cluster_view = None
        self._leaving_flag = False
        self._terminate_flag = False
        self.thread = Thread(target=self.main, name=plugin.__class__.__name__)
        self.force_leave = force_leave
        self.executor = futures.ThreadPoolExecutor(10)
        self.terminate_future = self.executor.submit(self.wait_for_terminate)

    def start_thread(self):
        self.thread.daemon = True
        self.thread.start()

    def terminate(self):
        self._terminate_flag = True
        self.thread.join()

    def wait_for_terminate(self):
        while not self._terminate_flag:
            sleep(1)

    def main(self):
        # Continue looping while the FSM is running.
        while self._fsm.is_running():
            # This blocks on changes to the cluster in etcd.
            _log.debug("Waiting for state change from etcd")
            cluster_view = self.read_from_etcd()
            if self._terminate_flag:
                break
            if cluster_view is not None:
                _log.debug("Got new state %s from etcd" % cluster_view)
                cluster_state = self.calculate_cluster_state(cluster_view)

                # This node can only leave the cluster if the cluster is in a stable
                # state. Check the leaving flag and the cluster state. If necessary,
                # set this node to WAITING_TO_LEAVE. Otherwise, kick the FSM.
                if self._leaving_flag and \
                        (cluster_state == STABLE or
                         cluster_state == LEAVE_PENDING or
                        (self.force_leave and cluster_state == STABLE_WITH_ERRORS)):
                    _log.info("Cluster is in a stable state, so leaving the cluster now")
                    new_state = WAITING_TO_LEAVE
                else:
                    local_state = self.calculate_local_state(cluster_view)
                    new_state = self._fsm.next(local_state,
                                               cluster_state,
                                               cluster_view)

                # If we have a new state, try and write it to etcd.
                if new_state is not None:
                    self.write_to_etcd(cluster_view, new_state)
                else:
                    _log.debug("No state change")
            else:
                _log.warning("read_from_etcd returned None, indicating a failure to get data from etcd")

        _log.info("Quitting FSM")
        self._fsm.quit()
        self.executor.shutdown(wait=False)

    def parse_cluster_view(self, view):
        try:
            return json.loads(view)
        except:
            return {}

    # This node has been asked to leave the cluster. Check if the cluster is in
    # a stable state, in which case we can leave. Otherwise, set a flag and
    # leave at the next available opportunity.
    def leave_cluster(self):
        _log.info("Trying to leave the cluster - plugin %s" % self._plugin.__class__.__name__)
        if not self._plugin.should_be_in_cluster():
            _log.info("No need to leave remote cluster - just exit")
            self._terminate_flag = True
            return
        result = self._client.read(self._key, quorum=True)
        cluster_view = self.parse_cluster_view(result.value)
        self._index = result.modifiedIndex

        cluster_state = self.calculate_cluster_state(cluster_view)

        if cluster_state == STABLE or \
           cluster_state == LEAVE_PENDING or \
                (self.force_leave and cluster_state == STABLE_WITH_ERRORS):
            _log.info("Cluster is in a stable state, so leaving the cluster immediately")
            self.write_to_etcd(cluster_view, WAITING_TO_LEAVE)
        else:
            _log.info("Can't leave the cluster immediately - will do so when the cluster next stabilises")
            self._leaving_flag = True

    def mark_node_failed(self):
        if not self._plugin.should_be_in_cluster():
            _log.debug("No need to mark failure in remote cluster - doing nothing")
            # We're just monitoring this cluster, not in it, so leaving is a
            # no-op
            return
        result = self._client.read(self._key, quorum=True)
        cluster_view = self.parse_cluster_view(result.value)
        self._index = result.modifiedIndex

        self.write_to_etcd(cluster_view, ERROR)

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
            if state != ERROR:
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
            if not oneOrMore:
                oneOrMore = []

            states_to_sum = zeroOrMore + oneOrMore

            total = sum([node_state_counts[i] for i in states_to_sum])
            has_minimum = sum([node_state_counts[i] for i in oneOrMore]) > 0

            return has_minimum and (total == node_count)

        if node_count == 0 and error_count == 0:
            return EMPTY
        elif node_state_counts[NORMAL] == node_count and error_count == 0:
            return STABLE
        elif node_state_counts[NORMAL] == node_count:
            return STABLE_WITH_ERRORS
        elif state_check(oneOrMore=[NORMAL, WAITING_TO_JOIN]):
            return JOIN_PENDING
        elif state_check(oneOrMore=[NORMAL, JOINING],
                         zeroOrMore=[NORMAL_ACKNOWLEDGED_CHANGE,
                                     JOINING_ACKNOWLEDGED_CHANGE]):
            return STARTED_JOINING
        elif state_check(oneOrMore=[NORMAL_ACKNOWLEDGED_CHANGE,
                                    JOINING_ACKNOWLEDGED_CHANGE],
                         zeroOrMore=[NORMAL_CONFIG_CHANGED,
                                     JOINING_CONFIG_CHANGED]):
            return JOINING_CONFIG_CHANGING
        elif state_check(oneOrMore=[NORMAL_CONFIG_CHANGED,
                                    JOINING_CONFIG_CHANGED],
                         zeroOrMore=[NORMAL]):
            return JOINING_RESYNCING
        elif state_check(oneOrMore=[NORMAL, WAITING_TO_LEAVE]):
            return LEAVE_PENDING
        elif state_check(oneOrMore=[NORMAL, LEAVING],
                         zeroOrMore=[NORMAL_ACKNOWLEDGED_CHANGE,
                                     LEAVING_ACKNOWLEDGED_CHANGE]):
            return STARTED_LEAVING
        elif state_check(oneOrMore=[NORMAL_ACKNOWLEDGED_CHANGE,
                                    LEAVING_ACKNOWLEDGED_CHANGE],
                         zeroOrMore=[NORMAL_CONFIG_CHANGED,
                                     LEAVING_CONFIG_CHANGED]):
            return LEAVING_CONFIG_CHANGING
        elif state_check(oneOrMore=[NORMAL_CONFIG_CHANGED,
                                    LEAVING_CONFIG_CHANGED],
                         zeroOrMore=[NORMAL, FINISHED]):
            return LEAVING_RESYNCING
        elif state_check(oneOrMore=[NORMAL, FINISHED]):
            return FINISHED_LEAVING
        else:
            # Cluster in unexpected state.
            return INVALID_CLUSTER_STATE

    # Returns the local node's state in the cluster, and None if the local node
    # is not in the cluster.
    def calculate_local_state(self, cluster_view):
        return cluster_view.get(self._ip)

    # Read the state of the cluster from etcd. Returns None if nothing could be
    # read.
    def read_from_etcd(self):
        cluster_view = None

        try:
            result = self._client.read(self._key, quorum=True)
            cluster_view = self.parse_cluster_view(result.value)

            # If the cluster view hasn't changed since we last saw it, then
            # wait for it to change before doing anything else.
            _log.info("Read cluster view {} from etcd, "
                      "comparing to last cluster view {}".format(
                          cluster_view,
                          self._last_cluster_view))
            if cluster_view == self._last_cluster_view:
                while not self._terminate_flag and self._fsm.is_running():
                    try:
                        _log.info("Watching for changes")
                        # Use a concurrent.futures.Executor to run the etcd poll
                        # asynchronously. This means that, if we're told to quit
                        # before etcd returns, we'll spot that we've been told
                        # to quit and do so.
                        result_future = self.executor.submit(self._client.read,
                                                             self._key,
                                                             wait=True,
                                                             waitIndex=result.modifiedIndex+1,
                                                             timeout=0,
                                                             recursive=False)
                        futures.wait([result_future, self.terminate_future], return_when=futures.FIRST_COMPLETED)
                        if result_future.done():
                            # This should always be the case unless we're about
                            # to quit
                            result = result_future.result(timeout=0)
                        else:
                            assert(self._terminate_flag)
                        break
                    except urllib3.exceptions.TimeoutError:
                        # Timeouts after 5 seconds are expected, so ignore them
                        # - unless we're terminating, we'll stay in the while
                        # loop and try again
                        pass
                    except etcd.EtcdException as e:
                        # We have seen timeouts getting raised as EtcdExceptions
                        # so catch these here too and treat them as timeouts if
                        # they indicate that the read timed out.
                        if "Read timed out" in e.message:
                            pass
                        else:
                            raise
                    except ValueError:
                        # The index isn't valid to watch on, probably because
                        # there has been a snapshot between the get and the
                        # watch. Just start the read again.
                        _log.info("etcd index {} is invalid, retrying".format(
                            result.modifiedIndex+1))
                        self.read_from_etcd()

                # Return if we're terminating.
                if self._terminate_flag:
                    return
                else:
                    cluster_view = self.parse_cluster_view(result.value)

            # Save off the index of the result we're using for when we write
            # back to etcd later.
            self._index = result.modifiedIndex
            self._last_cluster_view = cluster_view.copy()

        except etcd.EtcdKeyError:
            _log.info("Key {} doesn't exist in etcd yet".format(self._key))
            # If the key doesn't exist in etcd then there is currently no
            # cluster.
            cluster_view = {}
            self._index = None
            self._last_cluster_view = None
            if not self._plugin.should_be_in_cluster():
                # We're watching a key managed by another plugin, and it
                # doesn't exist yet - sleep to give the other plugin a chance to
                # create it
                sleep(self.PAUSE_BEFORE_RETRY)
        except Exception as e:
            # Catch-all error handler (for invalid requests, timeouts, etc -
            # start over.
            _log.error("{} caught {!r} when trying to read with index {}"
                       " - pause before retry".
                       format(self._ip, e, self._index))
            # Sleep briefly to avoid hammering a failed server
            sleep(self.PAUSE_BEFORE_RETRY)
            # The main loop (which reads from etcd in a loop) should call this
            # function again after we return, causing the read to be retried.

        return cluster_view

    # Write the new cluster view to etcd. We may be expecting to create the key
    # for the first time.
    def write_to_etcd(self, old_cluster_view, new_state, with_index=None):
        cluster_view = old_cluster_view.copy()

        # Update the cluster view based on new state information. If new_state
        # is a string then it refers to the new state of the local node.
        # Otherwise, it is an overall picture of the new cluster.
        if isinstance(new_state, str):
            cluster_view[self._ip] = new_state
        elif isinstance(new_state, dict):
            cluster_view = new_state

        _log.debug("Writing state %s into etcd" % cluster_view)
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
            # Our etcd write failed because someone got there before us.

            if isinstance(new_state, str):
                # We're just trying to update our own state, so it may be safe
                # to take the new state, update our own state in it, and retry.
                result = self._client.read(self._key, quorum=True)
                cluster_view = self.parse_cluster_view(result.value)

                # This isn't safe if someone else has changed our state for us,
                # or the overall deployment state has changed (in which case we
                # may want to change our state to something else, so check for
                # that.
                if ((new_state == ERROR) or
                    (cluster_view.get(self._ip) == old_cluster_view.get(self._ip) and
                    (self.calculate_cluster_state(cluster_view) ==
                     self.calculate_cluster_state(old_cluster_view)))):
                    self.write_to_etcd(cluster_view,
                                       new_state,
                                       with_index=result.modifiedIndex)
        except Exception as e:
            # Catch-all error handler (for invalid requests, timeouts, etc -
            # unset our state and start over.
            _log.error("{} caught {!r} when trying to write {} with index {}"
                       " - pause before retrying"
                .format(self._ip, e, json_data, self._index))
            # Setting last_cluster_view to None means that the next successful
            # read from etcd will trigger the state machine, which will mean
            # that any necessary work/state changes get retried.
            self._last_cluster_view = None
            # Sleep briefly to avoid hammering a failed server
            sleep(self.PAUSE_BEFORE_RETRY)
