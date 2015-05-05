#!/usr/bin/env python

import unittest
from mock import patch, call
from .mock_python_etcd import EtcdFactory, SlowMockEtcdClient
from metaswitch.clearwater.cluster_manager.etcd_synchronizer import EtcdSynchronizer
from metaswitch.clearwater.cluster_manager.synchronization_fsm import SyncFSM
from .dummy_plugin import DummyPlugin
from .contention_detecting_plugin import ContentionDetectingPlugin
from threading import Thread
from time import sleep
import json
from etcd import EtcdKeyError
import logging
import os
from .test_base import BaseClusterTest

class TestNewCluster(BaseClusterTest):

    @patch("etcd.Client", new=EtcdFactory)
    def test_new_cluster(self):
        sync1 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.1')
        sync2 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.2')
        sync3 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.3')
        mock_client = sync1._client
        for s in [sync1, sync2, sync3]:
            s.start_thread()
        self.wait_for_all_normal(mock_client, required_number=3)
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        for s in [sync1, sync2, sync3]:
            s.terminate()

    @patch("etcd.Client", new=EtcdFactory)
    def test_large_new_cluster(self):
        self.make_and_start_synchronizers(30)
        mock_client = self.syncs[0]._client
        self.wait_for_all_normal(mock_client, required_number=30, tries=300)
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual("normal", end.get("10.0.0.19"))
        self.assertEqual("normal", end.get("10.0.0.29"))
        self.close_synchronizers()


    @unittest.skipUnless(os.environ.get("SLOW"), "SLOW=T not set")
    @patch("etcd.Client", new=SlowMockEtcdClient)
    def test_large_new_cluster_with_delays(self):
        self.make_and_start_synchronizers(30)
        mock_client = self.syncs[0]._client
        self.wait_for_all_normal(mock_client, required_number=30, tries=300)
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual("normal", end.get("10.0.0.19"))
        self.assertEqual("normal", end.get("10.0.0.29"))
        self.close_synchronizers()
