#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

from .test_base import BaseQueueTest
from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import EtcdFactory
from metaswitch.clearwater.queue_manager.etcd_synchronizer import EtcdSynchronizer, WriteToEtcdStatus
from .plugin import TestPlugin
from mock import patch
from time import sleep
import json

alarms_patch = patch("metaswitch.clearwater.queue_manager.alarms.alarm_manager")

class RemoveFromQueueFailureTest(BaseQueueTest):
    @patch("etcd.Client", new=EtcdFactory)
    def setUp(self):
        alarms_patch.start()
        self._p = TestPlugin()
        self._e = EtcdSynchronizer(self._p, "10.0.0.1", "local", "clearwater", "node")
        self._e.WAIT_FOR_TIMER_POP = 0

    def remove_from_queue_helper(self):
        success = False

        for x in range(10):
            if self._e.remove_from_queue(False) == WriteToEtcdStatus.SUCCESS:
                success = True
                break
            sleep(1)

        if not success:
            print "Failed to successfully remove the node from the queue"

    # Tests that marking a node as failed moves it to the ERRORED list
    @patch("etcd.Client", new=EtcdFactory)
    def test_remove_from_queue_after_failure(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"}]}")
        self.remove_from_queue_helper()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(1, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(0, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.1-node", val.get("ERRORED")[0]["ID"])
        self.assertEqual("FAILURE", val.get("ERRORED")[0]["STATUS"])

    # Tests that marking a node as failed but when it is also the next node in the queue doesn't set it as errored
    @patch("etcd.Client", new=EtcdFactory)
    def test_remove_from_queue_after_failure_no_force(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [{\"ID\":\"10.0.0.3-node\",\"STATUS\":\"DONE\"}, {\"ID\":\"10.0.0.2-node\",\"STATUS\":\"DONE\"}], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"}, {\"ID\":\"10.0.0.1-node\",\"STATUS\":\"QUEUED\"}]}")
        self.remove_from_queue_helper()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(1, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(0, len(val.get("QUEUED")))

    # Tests that marking a node as failed but when it is also the next node in the queue doesn't set it as errored
    @patch("etcd.Client", new=EtcdFactory)
    def test_remove_from_queue_after_failure_force(self):
        self.set_initial_val("{\"FORCE\": true, \"ERRORED\": [{\"ID\":\"10.0.0.4-node\",\"STATUS\":\"UNRESPONSIVE\"}, {\"ID\":\"10.0.0.5-node\",\"STATUS\":\"FAILURE\"}], \"COMPLETED\": [{\"ID\":\"10.0.0.3-node\",\"STATUS\":\"DONE\"}, {\"ID\":\"10.0.0.2-node\",\"STATUS\":\"DONE\"}], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"}, {\"ID\":\"10.0.0.1-node\",\"STATUS\":\"QUEUED\"}]}")
        self.remove_from_queue_helper()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(2, len(val.get("ERRORED")))
        self.assertEqual(2, len(val.get("COMPLETED")))
        self.assertEqual(1, len(val.get("QUEUED")))

    @patch("etcd.Client", new=EtcdFactory)
    # Tests that marking a node as failed when it is in the queued list but not the next node does move it to the ERRORED list
    def test_remove_from_queue_after_failure_not_next_in_queue_force(self):
        self.set_initial_val("{\"FORCE\": true, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"}, {\"ID\":\"10.0.0.2-node\",\"STATUS\":\"QUEUED\"}, {\"ID\":\"10.0.0.1-node\",\"STATUS\":\"QUEUED\"}]}")
        self.remove_from_queue_helper()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(1, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(2, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.1-node", val.get("ERRORED")[0]["ID"])
        self.assertEqual("FAILURE", val.get("ERRORED")[0]["STATUS"])

    # Tests that marking a node as failed when it isn't the front of the queue doesn't change the JSON
    @patch("etcd.Client", new=EtcdFactory)
    def test_remove_from_queue_after_failure_not_front_of_queue_force(self):
        self.set_initial_val("{\"FORCE\": true, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.2-node\",\"STATUS\":\"PROCESSING\"},{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"QUEUED\"}]}")
        self.remove_from_queue_helper()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(0, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(2, len(val.get("QUEUED")))
