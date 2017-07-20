#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2015
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


from mock import patch
from metaswitch.clearwater.etcd_shared.test.mock_python_consul import ConsulFactory
import json
from .test_consul import BaseConsulBackedClusterTest
from .dummy_plugin import DummyWatcherPlugin
from metaswitch.clearwater.cluster_manager.consul_synchronizer import \
    ConsulSynchronizer
from time import sleep

class TestWatcherPlugin(BaseConsulBackedClusterTest):

    def setUp(self):
        BaseConsulBackedClusterTest.setUp(self)
        self.watcher_ip = "10.1.1.1"
        self.plugin = DummyWatcherPlugin(self.watcher_ip);

    def tearDown(self):
        self.close_synchronizers()

    @patch("consul.Consul", new=ConsulFactory)
    def test_watcher(self):
        """Create a new 3-node cluster with one plugin not in the cluster and
        check that the main three all end up in NORMAL state"""

        e = ConsulSynchronizer(self.plugin, self.watcher_ip)
        e.start_thread()

        self.make_and_start_synchronizers(3)
        mock_client = self.syncs[0]._client
        self.wait_for_all_normal(mock_client, required_number=3)

        # Pause for one second - the watcher plugin might be called just after
        # all other nodes enter 'normal' state
        sleep(1)
        self.assertTrue(self.plugin.on_stable_cluster_called)

        (_, resp) = mock_client.get("test")
        end = json.loads(resp.get("Value"))
        self.assertEqual("normal", end.get("10.0.0.0"))
        self.assertEqual("normal", end.get("10.0.0.1"))
        self.assertEqual("normal", end.get("10.0.0.2"))
        self.assertEqual(None, end.get("10.1.1.1"))

        e.terminate()

    @patch("consul.Consul")
    def test_leaving(self, client):
        """Create a plugin not in the cluster and try to leave the cluster.
        Nothing should be written to etcd."""
        e = ConsulSynchronizer(self.plugin, self.watcher_ip)
        e.start_thread()

        e.leave_cluster()
        e._client.put.assert_not_called()

        e.terminate()

    @patch("consul.Consul")
    def test_mark_failed(self, client):
        """Create a plugin not in the cluster and try to mark it as failed.
        Nothing should be written to etcd."""
        e = ConsulSynchronizer(self.plugin, self.watcher_ip)
        e.start_thread()

        e.mark_node_failed()
        e._client.put.assert_not_called()

        e.terminate()

