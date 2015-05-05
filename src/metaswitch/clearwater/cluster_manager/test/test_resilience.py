#!/usr/bin/env python

import unittest
from mock import patch, call
from .mock_python_etcd import ExceptionMockEtcdClient
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

class TestResilience(BaseClusterTest):

    @patch("etcd.Client", new=ExceptionMockEtcdClient)
    def test_resilience_to_exceptions(self):
        self.make_and_start_synchronizers(15)
        mock_client = self.syncs[0]._client
        self.wait_for_all_normal(mock_client, required_number=15, tries=300)
        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual("normal", end.get("10.0.0.14"))
        self.close_synchronizers()


