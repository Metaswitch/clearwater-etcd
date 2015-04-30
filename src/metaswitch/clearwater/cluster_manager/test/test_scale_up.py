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

class TestScaleUp(unittest.TestCase):
    def setUp(self):
        pass

    def wait_for_state(self, client, ip, state, tries=20):
        for i in range(tries):
            end = json.loads(client.get("/test").value)
            if end.get(ip) == state:
                return
            sleep(0.1)


    @patch("etcd.Client", new=MockEtcdClient)
    def test_scale_up(self):
        SyncFSM.DELAY = 0.1
        sync1 = EtcdSynchronizer(DummyPlugin(), '10.0.0.1')
        sync2 = EtcdSynchronizer(DummyPlugin(), '10.0.0.2')
        sync3 = EtcdSynchronizer(DummyPlugin(), '10.0.0.3')
        mock_client = sync1._client
        mock_client.write("/test", json.dumps({"10.0.0.1": "normal", "10.0.0.2": "normal"}))
        for s in [sync1, sync2, sync3]:
            thread = Thread(target=s.main)
            thread.daemon = True
            thread.start()
        self.wait_for_state(mock_client, '10.0.0.3', 'normal')
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
