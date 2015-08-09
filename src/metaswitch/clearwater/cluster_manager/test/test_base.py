#!/usr/bin/env python

# Project Clearwater - IMS in the Cloud
# Copyright (C) 2015 Metaswitch Networks Ltd
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version, along with the "Special Exception" for use of
# the program along with SSL, set forth below. This program is distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details. You should have received a copy of the GNU General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
# The author can be reached by email at clearwater@metaswitch.com or by
# post at Metaswitch Networks Ltd, 100 Church St, Enfield EN2 6BQ, UK
#
# Special Exception
# Metaswitch Networks Ltd  grants you permission to copy, modify,
# propagate, and distribute a work formed by combining OpenSSL with The
# Software, or a work derivative of such a combination, even if such
# copying, modification, propagation, or distribution would otherwise
# violate the terms of the GPL. You must comply with the GPL in all
# respects for all of the code used other than OpenSSL.
# "OpenSSL" means OpenSSL toolkit software distributed by the OpenSSL
# Project and licensed under the OpenSSL Licenses, or a work based on such
# software and licensed under the OpenSSL Licenses.
# "OpenSSL Licenses" means the OpenSSL License and Original SSLeay License
# under which the OpenSSL Project distributes the OpenSSL toolkit software,
# as those licenses appear in the file LICENSE-OPENSSL.


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
from mock import patch, MagicMock

alarms_patch = patch("metaswitch.clearwater.cluster_manager.alarms.issue_alarm", new=MagicMock)

class BaseClusterTest(unittest.TestCase):
    def setUp(self):
        SyncFSM.DELAY = 0.1
        CommonEtcdSynchronizer.PAUSE_BEFORE_RETRY = 0
        MockEtcdClient.clear()
        alarms_patch.start()
        self.syncs = []

    def wait_for_all_normal(self, client, required_number=-1, tries=20):
        for i in range(tries):
            value = None
            try:
                value = client.read_noexcept("/test").value
                end = json.loads(value)
                if all([v == "normal" for k, v in end.iteritems()]) and \
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

    def close_synchronizers(self):
        for s in self.syncs:
            s.terminate()
