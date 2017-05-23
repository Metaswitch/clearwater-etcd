#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import EtcdFactory
from metaswitch.clearwater.queue_manager.etcd_synchronizer import EtcdSynchronizer
from .plugin import TestNoTimerDelayPlugin
from mock import patch
from .test_base import BaseQueueTest

alarms_patch = patch("metaswitch.clearwater.queue_manager.alarms.alarm_manager")

class TimersTest(BaseQueueTest):
    @patch("etcd.Client", new=EtcdFactory)
    def setUp(self):
        alarms_patch.start()
        self._p = TestNoTimerDelayPlugin()
        self._e = EtcdSynchronizer(self._p, "10.0.0.1", "local", "clearwater", "node")

    # Test that when a timer pops for the current node it marks the node as failed
    def test_this_node_timer_pop(self):
        # Write some initial data into the key
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"}]}")

        def pass_criteria(val):
            return (1 == len(val.get("ERRORED"))) and \
                   (0 == len(val.get("COMPLETED"))) and \
                   (0 == len(val.get("QUEUED"))) and \
                   ("10.0.0.1-node" == val.get("ERRORED")[0]["ID"]) and \
                   ("UNRESPONSIVE" == val.get("ERRORED")[0]["STATUS"])

        self.assertTrue(self.wait_for_success_or_fail(pass_criteria))

    @patch("etcd.Client", new=EtcdFactory)
    # Test that when a timer pops for another node it marks the other node as failed
    def test_other_node_timer_pop(self):
        # Write some initial data into the key
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.2-node\",\"STATUS\":\"PROCESSING\"}]}")

        def pass_criteria(val):
            return (1 == len(val.get("ERRORED"))) and \
                   (0 == len(val.get("COMPLETED"))) and \
                   (0 == len(val.get("QUEUED"))) and \
                   ("10.0.0.2-node" == val.get("ERRORED")[0]["ID"]) and \
                   ("UNRESPONSIVE" == val.get("ERRORED")[0]["STATUS"])

        self.assertTrue(self.wait_for_success_or_fail(pass_criteria))

    # Test that when a timer pops when force is true it doesn't clear the queue
    def test_timer_pop_force(self):
        # Write some initial data into the key
        self.set_initial_val("{\"FORCE\": true, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"},{\"ID\":\"10.0.0.2-node\",\"STATUS\":\"QUEUED\"}]}")

        def pass_criteria(val):
            return (2 == len(val.get("ERRORED"))) and \
                   (0 == len(val.get("COMPLETED"))) and \
                   (0 == len(val.get("QUEUED"))) and \
                   ("10.0.0.1-node" == val.get("ERRORED")[0]["ID"]) and \
                   ("UNRESPONSIVE" == val.get("ERRORED")[0]["STATUS"]) and \
                   ("10.0.0.2-node" == val.get("ERRORED")[1]["ID"]) and \
                   ("UNRESPONSIVE" == val.get("ERRORED")[1]["STATUS"])

        self.assertTrue(self.wait_for_success_or_fail(pass_criteria))

    # Test that when a timer pops when force is false it does clear the queue
    def test_timer_pop_no_force(self):
        # Write some initial data into the key
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"},{\"ID\":\"10.0.0.2-node\",\"STATUS\":\"PROCESSING\"}]}")

        def pass_criteria(val):
            return (1 == len(val.get("ERRORED"))) and \
                   (0 == len(val.get("COMPLETED"))) and \
                   (0 == len(val.get("QUEUED"))) and \
                   ("10.0.0.1-node" == val.get("ERRORED")[0]["ID"]) and \
                   ("UNRESPONSIVE" == val.get("ERRORED")[0]["STATUS"])

        self.assertTrue(self.wait_for_success_or_fail(pass_criteria))
