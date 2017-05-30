#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2015
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


from mock import patch
from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import EtcdFactory
import json
from .test_base import BaseClusterTest
from .dummy_plugin import DummyWatcherPlugin
from metaswitch.clearwater.cluster_manager.etcd_synchronizer import \
    EtcdSynchronizer
from time import sleep

class TestWatcherPlugin(BaseClusterTest):

    def setUp(self):
        BaseClusterTest.setUp(self)
        self.watcher_ip = "10.1.1.1"
        self.plugin = DummyWatcherPlugin(self.watcher_ip);

    def tearDown(self):
        self.close_synchronizers()

    @patch("etcd.Client", new=EtcdFactory)
    def test_watcher(self):
        """Create a new 3-node cluster with one plugin not in the cluster and
        check that the main three all end up in NORMAL state"""

        e = EtcdSynchronizer(self.plugin, self.watcher_ip)
        e.start_thread()

        self.make_and_start_synchronizers(3)
        mock_client = self.syncs[0]._client
        self.wait_for_all_normal(mock_client, required_number=3)

        # Pause for one second - the watcher plugin might be called just after
        # all other nodes enter 'normal' state
        sleep(1)
        self.assertTrue(self.plugin.on_stable_cluster_called)

        end = json.loads(mock_client.read("/test").value)
        self.assertEqual("normal", end.get("10.0.0.0"))
        self.assertEqual("normal", end.get("10.0.0.1"))
        self.assertEqual("normal", end.get("10.0.0.2"))
        self.assertEqual(None, end.get("10.1.1.1"))

        e.terminate()

    @patch("etcd.Client")
    def test_leaving(self, client):
        """Create a plugin not in the cluster and try to leave the cluster.
        Nothing should be written to etcd."""
        e = EtcdSynchronizer(self.plugin, self.watcher_ip)
        e.start_thread()

        e.leave_cluster()
        e._client.write.assert_not_called()

        e.terminate()

    @patch("etcd.Client")
    def test_mark_failed(self, client):
        """Create a plugin not in the cluster and try to mark it as failed.
        Nothing should be written to etcd."""
        e = EtcdSynchronizer(self.plugin, self.watcher_ip)
        e.start_thread()

        e.mark_node_failed()
        e._client.write.assert_not_called()

        e.terminate()

