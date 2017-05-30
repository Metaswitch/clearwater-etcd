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
from metaswitch.clearwater.cluster_manager.null_plugin import NullPlugin
from .dummy_plugin import DummyPlugin
from .fail_partway_through_plugin import FailPlugin
from time import sleep
import json
from .test_base import BaseClusterTest


class TestNodeFailure(BaseClusterTest):

    @patch("etcd.Client", new=EtcdFactory)
    def test_failure(self):

        # Create synchronisers, using a FailPlugin for one which will crash and
        # not complete (simulating a failed node)
        sync1 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.1')
        sync2 = EtcdSynchronizer(FailPlugin(None), '10.0.0.2')
        sync3 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.3')
        mock_client = sync1._client
        for s in [sync1, sync2, sync3]:
            s.start_thread()

        # After a few seconds, the scale-up will still not have completed
        sleep(3)
        end = json.loads(mock_client.read("/test").value)
        self.assertNotEqual("normal", end.get("10.0.0.1"))
        self.assertNotEqual("normal", end.get("10.0.0.2"))
        self.assertNotEqual("normal", end.get("10.0.0.3"))

        # Start a synchroniser to take 10.0.0.2's place
        sync2.terminate()
        error_syncer = EtcdSynchronizer(NullPlugin('/test'),
                                        '10.0.0.2',
                                        force_leave=True)
        error_syncer.mark_node_failed()
        error_syncer.leave_cluster()
        error_syncer.start_thread()

        # 10.0.0.2 will be removed from the cluster, and the cluster will
        # stabilise
        self.wait_for_all_normal(mock_client, required_number=2, tries=50)
        end = json.loads(mock_client.read("/test").value)
        self.assertEqual("normal", end.get("10.0.0.1"))
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual(None, end.get("10.0.0.2"))
        for s in [sync1, sync3, error_syncer]:
            s.terminate()
