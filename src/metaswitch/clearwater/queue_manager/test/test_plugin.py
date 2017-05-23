#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import EtcdFactory
from metaswitch.clearwater.queue_manager.etcd_synchronizer import EtcdSynchronizer
from .plugin import TestFrontOfQueueCallbackPlugin
from mock import patch
from time import sleep
from .test_base import BaseQueueTest

alarms_patch = patch("metaswitch.clearwater.queue_manager.alarms.alarm_manager")

class PluginTest(BaseQueueTest):
    @patch("etcd.Client", new=EtcdFactory)
    def setUp(self):
        alarms_patch.start()
        self._p = TestFrontOfQueueCallbackPlugin()
        self._e = EtcdSynchronizer(self._p, "10.0.0.1", "local", "clearwater", "node")
        self._e.WAIT_FOR_TIMER_POP = 0

    def check_plugin_called(self):
        for x in range(10):
            if self._p._at_front_of_queue_called:
                return True
            sleep(1)
        print "Plugin's at_front_of_queue method hasn't been called"

    # Tests that a node at the front of the queue calls into its plugin
    def test_front_of_queue_processing(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": []}")

        # It's unpleasant using sleeps here, but there's no nice
        # way to check that the synchronizer has started
        sleep(2)

        # Check that the plugin hasn't been called
        self.assertFalse(self._p._at_front_of_queue_called)

        # Write a new value into etcd, and check that the plugin is called
        self._e._client.write("/clearwater/local/configuration/queue_test", "{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"QUEUED\"}]}")
        self.assertTrue(self.check_plugin_called())
