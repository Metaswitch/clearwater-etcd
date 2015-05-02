#!/usr/bin/env python

import unittest
from .mock_python_etcd import MockEtcdClient
from metaswitch.clearwater.cluster_manager.synchronization_fsm import SyncFSM
from metaswitch.clearwater.cluster_manager.etcd_synchronizer import \
    EtcdSynchronizer
from .dummy_plugin import DummyPlugin
from time import sleep
import json
from etcd import EtcdKeyError


class BaseClusterTest(unittest.TestCase):
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
