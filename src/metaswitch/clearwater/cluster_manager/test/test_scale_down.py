#!/usr/bin/env python

from mock import patch
from .mock_python_etcd import EtcdFactory
from metaswitch.clearwater.cluster_manager.etcd_synchronizer \
    import EtcdSynchronizer
from .dummy_plugin import DummyPlugin
import json
from .test_base import BaseClusterTest


class TestScaleDown(BaseClusterTest):

    @patch("etcd.Client", new=EtcdFactory)
    def test_scale_down(self):
        # Start with a stable cluster of two nodes
        sync1 = EtcdSynchronizer(DummyPlugin(None), '10.0.1.1')
        sync2 = EtcdSynchronizer(DummyPlugin(None), '10.0.1.2')
        mock_client = sync1._client
        mock_client.write("/test", json.dumps({"10.0.1.1": "normal",
                                               "10.0.1.2": "normal"}))
        for s in [sync1, sync2]:
            s.start_thread()

        # Make the second node leave
        sync2.leave_cluster()
        sync2.thread.join(20)
        self.wait_for_all_normal(mock_client, required_number=1)

        # Check that it's left and the cluster is stable
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual(None, end.get("10.0.1.2"))
        self.assertEqual("normal", end.get("10.0.1.1"))
        sync1.terminate()
