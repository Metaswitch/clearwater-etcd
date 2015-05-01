#!/usr/bin/env python

import unittest
from mock import patch, call
from .mock_python_etcd import MockEtcdClient
from metaswitch.clearwater.cluster_manager.etcd_synchronizer import EtcdSynchronizer
from metaswitch.clearwater.cluster_manager.synchronization_fsm import SyncFSM
from .dummy_plugin import DummyPlugin
from threading import Thread
from time import sleep
import json
from etcd import EtcdKeyError

class TestScaleUp(unittest.TestCase):
    def setUp(self):
        pass

    def wait_for_state(self, client, ip, state, tries=20):
        for i in range(tries):
            try:
                end = json.loads(client.get("/test").value)
                if end.get(ip) == state:
                    return
            except EtcdKeyError:
                pass
            sleep(0.1)


    @patch("etcd.Client", new=MockEtcdClient)
    @patch("metaswitch.clearwater.cluster_manager.synchronization_fsm.TooLongAlarm")
    def test_new_cluster(self, alarm):
        SyncFSM.DELAY = 0.1
        sync1 = EtcdSynchronizer(DummyPlugin(), '10.0.0.1')
        sync2 = EtcdSynchronizer(DummyPlugin(), '10.0.0.2')
        sync3 = EtcdSynchronizer(DummyPlugin(), '10.0.0.3')
        mock_client = sync1._client
        for s in [sync1, sync2, sync3]:
            s.start_thread()
        self.wait_for_state(mock_client, '10.0.0.3', 'normal')
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        for s in [sync1, sync2, sync3]:
            s.terminate()


    @patch("etcd.Client", new=MockEtcdClient)
    @patch("metaswitch.clearwater.cluster_manager.synchronization_fsm.TooLongAlarm")
    def test_scale_up(self, alarm):
        SyncFSM.DELAY = 0.1
        sync1 = EtcdSynchronizer(DummyPlugin(), '10.0.0.1')
        sync2 = EtcdSynchronizer(DummyPlugin(), '10.0.0.2')
        sync3 = EtcdSynchronizer(DummyPlugin(), '10.0.0.3')
        mock_client = sync1._client
        mock_client.write("/test", json.dumps({"10.0.0.1": "normal", "10.0.0.2": "normal"}))
        for s in [sync1, sync2, sync3]:
            s.start_thread()
        self.wait_for_state(mock_client, '10.0.0.3', 'normal')
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        for s in [sync1, sync2, sync3]:
            s.terminate()


    @patch("etcd.Client", new=MockEtcdClient)
    @patch("metaswitch.clearwater.cluster_manager.synchronization_fsm.TooLongAlarm")
    def test_scale_down(self, alarm):
        SyncFSM.DELAY = 0.1
        sync1 = EtcdSynchronizer(DummyPlugin(), '10.0.1.1')
        sync2 = EtcdSynchronizer(DummyPlugin(), '10.0.1.2')
        mock_client = sync1._client
        mock_client.write("/test", json.dumps({"10.0.1.1": "normal", "10.0.1.2": "normal"}))
        for s in [sync1, sync2]:
            s.start_thread()
        sync2.leave_cluster()
        sync2.thread.join(20)
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual(None, end.get("10.0.1.2"))
        sync1.terminate()


    @patch("etcd.Client", new=MockEtcdClient)
    @patch("metaswitch.clearwater.cluster_manager.synchronization_fsm.TooLongAlarm")
    def test_two_new_nodes(self, alarm):
        SyncFSM.DELAY = 0.2
        sync1 = EtcdSynchronizer(DummyPlugin(), '10.0.0.1')
        sync2 = EtcdSynchronizer(DummyPlugin(), '10.0.0.2')
        sync3 = EtcdSynchronizer(DummyPlugin(), '10.0.0.3')
        sync4 = EtcdSynchronizer(DummyPlugin(), '10.0.0.4')
        mock_client = sync1._client
        mock_client.write("/test", json.dumps({"10.0.0.1": "normal", "10.0.0.2": "normal"}))
        for s in [sync1, sync2, sync3, sync4]:
            s.start_thread()
        self.wait_for_state(mock_client, '10.0.0.3', 'normal')
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual("normal", end.get("10.0.0.4"))
        for s in [sync1, sync2, sync3, sync4]:
            s.terminate()
