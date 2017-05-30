#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


import unittest
from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import MockEtcdClient
from metaswitch.clearwater.cluster_manager.synchronization_fsm import SyncFSM
from metaswitch.clearwater.cluster_manager.etcd_synchronizer import \
    EtcdSynchronizer
from metaswitch.clearwater.etcd_shared.common_etcd_synchronizer import \
    CommonEtcdSynchronizer
from .dummy_plugin import DummyPlugin
from time import sleep
import json
from etcd import EtcdKeyError
from mock import patch

alarms_patch = patch("metaswitch.clearwater.cluster_manager.alarms.alarm_manager")

class BaseClusterTest(unittest.TestCase):
    def setUp(self):
        SyncFSM.DELAY = 0.1
        CommonEtcdSynchronizer.PAUSE_BEFORE_RETRY_ON_EXCEPTION = 0
        CommonEtcdSynchronizer.PAUSE_BEFORE_RETRY_ON_MISSING_KEY = 0
        CommonEtcdSynchronizer.TIMEOUT_ON_WATCH = 0
        MockEtcdClient.clear()
        alarms_patch.start()
        self.syncs = []

    def wait_for_all_normal(self, client, required_number=-1, tries=20):
        for i in range(tries):
            value = None
            try:
                value = client.read_noexcept("/test").value
                end = json.loads(value)
                if all([v == "normal" for v in end.itervalues()]) and \
                   (required_number == -1 or len(end) == required_number):
                    return
            except EtcdKeyError:
                pass
            except ValueError:
                print "Got bad JSON '{}'".format(value)
            sleep(0.1)

    def make_and_start_synchronizers(self, num, klass=DummyPlugin):
        ips = ["10.0.0.%s" % d for d in range(num)]
        self.syncs = [EtcdSynchronizer(klass(ip), ip) for ip in ips]
        for s in self.syncs:
            s.start_thread()
        sleep(1) # Allow cluster to stabilise

    def close_synchronizers(self):
        for s in self.syncs:
            s.terminate()
