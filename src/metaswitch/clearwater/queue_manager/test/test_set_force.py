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

class SetForceQueueTest(BaseQueueTest):
    @patch("etcd.Client", new=EtcdFactory)
    def setUp(self):
        alarms_patch.start()
        self._p = TestPlugin()
        self._e = EtcdSynchronizer(self._p, "10.0.0.1", "local", "clearwater", "node")
        self._e.WAIT_FOR_TIMER_POP = 0

    def set_force_helper(self, force):
        success = False

        for x in range(10):
            if self._e.set_force(force) == WriteToEtcdStatus.SUCCESS:
                success = True
                break
            sleep(1)

        if not success:
            print "Failed to successfully run set_force"

    # Test that the FORCE value in the JSON can be correctly toggled
    def test_set_force(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": []}")

        self.set_force_helper(False)
        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertFalse(val.get("FORCE"))

        self.set_force_helper(True)
        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertTrue(val.get("FORCE"))

        self.set_force_helper(False)
        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertFalse(val.get("FORCE"))
