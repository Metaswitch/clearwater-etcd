#!/usr/bin/env python

import unittest
from mock import patch, call
from .mock_python_etcd import EtcdFactory, SlowMockEtcdClient
from metaswitch.clearwater.cluster_manager.etcd_synchronizer import EtcdSynchronizer
from metaswitch.clearwater.cluster_manager.synchronization_fsm import SyncFSM
from metaswitch.clearwater.cluster_manager.null_plugin import NullPlugin
from .dummy_plugin import DummyPlugin
from .fail_partway_through_plugin import FailPlugin
from .contention_detecting_plugin import ContentionDetectingPlugin
from threading import Thread
from time import sleep
import json
from etcd import EtcdKeyError
import logging
import os
from .test_base import BaseClusterTest

class TestNodeFailure(BaseClusterTest):

    @patch("etcd.Client", new=EtcdFactory)
    def test_failure(self):
        sync1 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.1')
        sync2 = EtcdSynchronizer(FailPlugin(None), '10.0.0.2')
        sync3 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.3')
        mock_client = sync1._client
        for s in [sync1, sync2, sync3]:
            s.start_thread()

        # After a few seconds, the scale-up will still not have completed
        sleep(3)
        end = json.loads(mock_client.get("/test").value)
        self.assertNotEqual("normal", end.get("10.0.0.1"))
        self.assertNotEqual("normal", end.get("10.0.0.2"))
        self.assertNotEqual("normal", end.get("10.0.0.3"))
        sync2.terminate()

        # Start a synchroniser to take 10.0.0.2's place
        error_syncer = EtcdSynchronizer(NullPlugin('/test'), '10.0.0.2', force_leave=True)
        error_syncer.mark_node_failed()
        error_syncer.leave_cluster()
        error_syncer.start_thread()
        sleep(3)
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.1"))
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual(None, end.get("10.0.0.2"))
        for s in [sync1, sync3]:
            s.terminate()
