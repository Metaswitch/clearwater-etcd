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

class TestScaleUp(unittest.TestCase):
    def setUp(self):
        SyncFSM.DELAY = 0.1
        MockEtcdClient.clear()

    def wait_for_all_normal(self, client, required_number=-1, tries=20):
        for i in range(tries):
            try:
                end = json.loads(client.get("/test").value)
                if all([v == "normal" for k, v in end.iteritems()]) and \
                   (required_number == -1 or len(end) == required_number):
                    return
            except EtcdKeyError:
                pass
            sleep(0.1)


    def make_and_start_synchronizers(self, num, klass=DummyPlugin):
        ips = ["10.0.0.%s" % d for d in range(num)]
        self.syncs = [EtcdSynchronizer(klass(ip), ip) for ip in ips]
        for s in self.syncs:
            s.start_thread()

    def close_synchronizers(self):
        for s in self.syncs:
            s.terminate()

    @patch("etcd.Client", new=SlowMockEtcdClient)
    @patch("metaswitch.clearwater.cluster_manager.synchronization_fsm.TooLongAlarm")
    def test_large_cluster(self, alarm):
        self.make_and_start_synchronizers(30)
        mock_client = self.syncs[0]._client
        self.wait_for_all_normal(mock_client, required_number=30, tries=300)
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual("normal", end.get("10.0.0.19"))
        self.assertEqual("normal", end.get("10.0.0.29"))
        self.close_synchronizers()

    @patch("etcd.Client", new=SlowMockEtcdClient)
    @patch("metaswitch.clearwater.cluster_manager.synchronization_fsm.TooLongAlarm")
    def test_write_contention(self, alarm):
        self.make_and_start_synchronizers(30, klass=ContentionDetectingPlugin)
        mock_client = self.syncs[0]._client
        self.wait_for_all_normal(mock_client, required_number=30, tries=300)
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual("normal", end.get("10.0.0.19"))
        self.assertEqual("normal", end.get("10.0.0.29"))
        self.close_synchronizers()



    @patch("etcd.Client", new=MockEtcdClient)
    @patch("metaswitch.clearwater.cluster_manager.synchronization_fsm.TooLongAlarm")
    def test_new_cluster(self, alarm):
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


    @patch("etcd.Client", new=MockEtcdClient)
    @patch("metaswitch.clearwater.cluster_manager.synchronization_fsm.TooLongAlarm")
    def test_scale_up(self, alarm):
        sync1 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.1')
        sync2 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.2')
        sync3 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.3')
        mock_client = sync1._client
        mock_client.write("/test", json.dumps({"10.0.0.1": "normal", "10.0.0.2": "normal"}))
        for s in [sync1, sync2, sync3]:
            s.start_thread()
        self.wait_for_all_normal(mock_client, required_number=3)
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        for s in [sync1, sync2, sync3]:
            s.terminate()


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


    @patch("etcd.Client", new=MockEtcdClient)
    @patch("metaswitch.clearwater.cluster_manager.synchronization_fsm.TooLongAlarm")
    def test_two_new_nodes(self, alarm):
        sync1 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.1')
        sync2 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.2')
        sync3 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.3')
        sync4 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.4')
        mock_client = sync1._client
        mock_client.write("/test", json.dumps({"10.0.0.1": "normal", "10.0.0.2": "normal"}))
        for s in [sync1, sync2, sync3, sync4]:
            s.start_thread()
        self.wait_for_all_normal(mock_client, required_number=4)
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual("normal", end.get("10.0.0.4"))
        for s in [sync1, sync2, sync3, sync4]:
            s.terminate()
