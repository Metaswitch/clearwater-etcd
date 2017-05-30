#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2015
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


from mock import patch
from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import EtcdFactory
from metaswitch.clearwater.cluster_manager.etcd_synchronizer \
    import EtcdSynchronizer
from .dummy_plugin import DummyPlugin
import json
from .test_base import BaseClusterTest
from time import sleep


class TestScaleDown(BaseClusterTest):

    @patch("etcd.Client", new=EtcdFactory)
    def test_scale_down(self):
        # Start with a stable cluster of four nodes
        syncs = [EtcdSynchronizer(DummyPlugin(None), ip) for ip in
                 ['10.0.1.1',
                  '10.0.1.2',
                  '10.0.1.3',
                  '10.0.1.4',
                  ]]
        mock_client = syncs[0]._client
        mock_client.write("/test", json.dumps({"10.0.1.1": "normal",
                                               "10.0.1.2": "normal",
                                               "10.0.1.3": "normal",
                                               "10.0.1.4": "normal",
                                               }))
        for s in syncs:
            s.start_thread()

        # Allow the cluster to stabilise, then make the second and fourth nodes leave
        sleep(1)
        syncs[1].leave_cluster()
        syncs[3].leave_cluster()

        self.wait_for_all_normal(mock_client, required_number=2, tries=50)

        # Check that it's left and the cluster is stable
        end = json.loads(mock_client.read("/test").value)
        self.assertEqual("normal", end.get("10.0.1.1"))
        self.assertEqual("normal", end.get("10.0.1.3"))
        self.assertEqual(None, end.get("10.0.1.2"))
        self.assertEqual(None, end.get("10.0.1.4"))

        for s in syncs:
            s.terminate()
