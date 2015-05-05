#!/usr/bin/env python

from mock import patch
from .mock_python_etcd import EtcdFactory
from metaswitch.clearwater.cluster_manager.etcd_synchronizer \
    import EtcdSynchronizer
from .dummy_plugin import DummyPlugin
import json
from .test_base import BaseClusterTest


class TestScaleUp(BaseClusterTest):

    @patch("etcd.Client", new=EtcdFactory)
    def test_scale_up(self):
        # Create an existing cluster of two nodes, and a third new node
        sync1 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.1')
        sync2 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.2')
        sync3 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.3')
        mock_client = sync1._client
        mock_client.write("/test", json.dumps({"10.0.0.1": "normal",
                                               "10.0.0.2": "normal"}))
        for s in [sync1, sync2, sync3]:
            s.start_thread()

        # Check that the third node joins the cluster
        self.wait_for_all_normal(mock_client, required_number=3)
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        for s in [sync1, sync2, sync3]:
            s.terminate()

    @patch("etcd.Client", new=EtcdFactory)
    def test_two_new_nodes(self):
        # Create an existing cluster of two nodes, and a third and fourth new
        # node at the same time
        sync1 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.1')
        sync2 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.2')
        sync3 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.3')
        sync4 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.4')
        mock_client = sync1._client
        mock_client.write("/test", json.dumps({"10.0.0.1": "normal",
                                               "10.0.0.2": "normal"}))
        for s in [sync1, sync2, sync3, sync4]:
            s.start_thread()

        # Check that the third and fourth nodes join the cluster
        self.wait_for_all_normal(mock_client, required_number=4)
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual("normal", end.get("10.0.0.4"))
        for s in [sync1, sync2, sync3, sync4]:
            s.terminate()
