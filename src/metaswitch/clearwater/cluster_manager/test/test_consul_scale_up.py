#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2015
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


from mock import patch
from metaswitch.clearwater.etcd_shared.test.mock_python_consul import ConsulFactory
from metaswitch.clearwater.cluster_manager.consul_synchronizer \
    import ConsulSynchronizer
from .dummy_plugin import DummyPlugin
import json
from .test_consul import BaseConsulBackedClusterTest


class TestConsulScaleUp(BaseConsulBackedClusterTest):

    @patch("consul.Consul", new=ConsulFactory)
    def test_scale_up(self):
        # Create an existing cluster of two nodes, and a third new node
        sync1 = ConsulSynchronizer(DummyPlugin(None), '10.0.0.1')
        sync2 = ConsulSynchronizer(DummyPlugin(None), '10.0.0.2')
        sync3 = ConsulSynchronizer(DummyPlugin(None), '10.0.0.3')
        mock_client = sync1._client
        mock_client.put("test", json.dumps({"10.0.0.1": "normal",
                                            "10.0.0.2": "normal"}))
        for s in [sync1, sync2, sync3]:
            s.start_thread()

        # Check that the third node joins the cluster
        self.wait_for_all_normal(mock_client, required_number=3)
        (_, resp) = mock_client.get("test")
        end = json.loads(resp.get("Value"))
        self.assertEqual("normal", end.get("10.0.0.3"))
        for s in [sync1, sync2, sync3]:
            s.terminate()

    @patch("consul.Consul", new=ConsulFactory)
    def test_two_new_nodes(self):
        # Create an existing cluster of two nodes, and a third and fourth new
        # node at the same time
        sync1 = ConsulSynchronizer(DummyPlugin(None), '10.0.0.1')
        sync2 = ConsulSynchronizer(DummyPlugin(None), '10.0.0.2')
        sync3 = ConsulSynchronizer(DummyPlugin(None), '10.0.0.3')
        sync4 = ConsulSynchronizer(DummyPlugin(None), '10.0.0.4')
        mock_client = sync1._client
        mock_client.put("test", json.dumps({"10.0.0.1": "normal",
                                            "10.0.0.2": "normal"}))
        for s in [sync1, sync2, sync3, sync4]:
            s.start_thread()

        # Check that the third and fourth nodes join the cluster
        self.wait_for_all_normal(mock_client, required_number=4)
        (_, resp) = mock_client.get("test")
        end = json.loads(resp.get("Value"))
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual("normal", end.get("10.0.0.4"))
        for s in [sync1, sync2, sync3, sync4]:
            s.terminate()
