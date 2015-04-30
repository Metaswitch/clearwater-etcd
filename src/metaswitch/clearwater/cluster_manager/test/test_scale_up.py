#!/usr/bin/env python

import unittest
from mock import patch, call
from .mock_python_etcd import MockEtcdClient
from metaswitch.clearwater.cluster_manager.synchronization_fsm import FakeEtcdSynchronizer
from .dummy_plugin import DummyPlugin
from threading import Thread
from time import sleep

class TestScaleUp(unittest.TestCase):
    def setUp(self):
        pass

    @patch("etcd.Client", new=MockEtcdClient)
    def test_scale_up(self):
        sync = FakeEtcdSynchronizer(DummyPlugin(), '10.0.0.3')
        mock_client = sync.client
        mock_client.write("/test", str({'10.0.0.1': 'normal', '10.0.0.2': 'normal'}))
        thread = Thread(target=sync.main)
        thread.start()
        sleep(2)
        self.assertIn('10.0.0.3', mock_client.get("/test").value)

