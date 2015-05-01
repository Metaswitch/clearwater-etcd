#!/usr/bin/env python

import unittest
from mock import patch, call
from .mock_python_etcd import MockEtcdClient, SlowMockEtcdClient
from metaswitch.clearwater.cluster_manager.etcd_synchronizer import EtcdSynchronizer
from metaswitch.clearwater.cluster_manager.synchronization_fsm import SyncFSM
from .dummy_plugin import DummyPlugin
from .contention_detecting_plugin import ContentionDetectingPlugin
from threading import Thread
from time import sleep
import json
from etcd import EtcdKeyError
import logging
from .test_base import BaseClusterTest

class TestScaleDown(BaseClusterTest):

    @patch("etcd.Client", new=MockEtcdClient)
    @patch("metaswitch.clearwater.cluster_manager.synchronization_fsm.TooLongAlarm")
    def test_scale_down(self, alarm):
        sync1 = EtcdSynchronizer(DummyPlugin(None), '10.0.1.1')
        sync2 = EtcdSynchronizer(DummyPlugin(None), '10.0.1.2')
        mock_client = sync1._client
        mock_client.write("/test", json.dumps({"10.0.1.1": "normal", "10.0.1.2": "normal"}))
        for s in [sync1, sync2]:
            s.start_thread()
        sync2.leave_cluster()
        sync2.thread.join(20)
        self.wait_for_all_normal(mock_client, required_number=2)
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual(None, end.get("10.0.1.2"))
        sync1.terminate()
