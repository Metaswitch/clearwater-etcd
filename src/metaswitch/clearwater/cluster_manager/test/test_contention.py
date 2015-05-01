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
import os
from .test_base import BaseClusterTest

class TestContention(BaseClusterTest):

    @unittest.skipUnless(os.environ.get("SLOW"), "SLOW=T not set")
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

