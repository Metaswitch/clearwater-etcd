#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2016
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

class RemoveFromQueueSuccessTest(BaseQueueTest):
    @patch("etcd.Client", new=EtcdFactory)
    def setUp(self):
        alarms_patch.start()
        self._p = TestPlugin()
        self._e = EtcdSynchronizer(self._p, "10.0.0.1", "local", "clearwater", "node")
        self._e.WAIT_FOR_TIMER_POP = 0

    def remove_from_queue_helper(self):
        success = False

        for x in range(10):
            if self._e.remove_from_queue(True) == WriteToEtcdStatus.SUCCESS:
                success = True
                break
            sleep(1)

        if not success:
            print "Failed to successfully remove the node from the queue"

    # Test that marking a node as successful moves it to the COMPLETED list
    @patch("etcd.Client", new=EtcdFactory)
    def test_remove_from_queue_success(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"}, {\"ID\":\"10.0.0.2-node\",\"STATUS\":\"QUEUED\"}]}")
        self.remove_from_queue_helper()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(0, len(val.get("ERRORED")))
        self.assertEqual(1, len(val.get("COMPLETED")))
        self.assertEqual(1, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.1-node", val.get("COMPLETED")[0]["ID"])
        self.assertEqual("DONE", val.get("COMPLETED")[0]["STATUS"])

    # Test that marking a node as successful when it is still in the queue doesn't move it to the COMPLETED list (but does take out the first entry)
    @patch("etcd.Client", new=EtcdFactory)
    def test_remove_from_queue_success_still_in_queue(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"},{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"QUEUED\"}]}")
        self.remove_from_queue_helper()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(0, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(1, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[0]["ID"])

    # Test that calling this method when the node isn't at the front of the
    # doesn't change the queue
    @patch("etcd.Client", new=EtcdFactory)
    def test_remove_from_queue_success_not_front_of_queue(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"UNRESPONSIVE\"}], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.2-node\",\"STATUS\":\"PROCESSING\"}]}")
        self.remove_from_queue_helper()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(1, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(1, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.2-node", val.get("QUEUED")[0]["ID"])
        self.assertEqual("PROCESSING", val.get("QUEUED")[0]["STATUS"])
