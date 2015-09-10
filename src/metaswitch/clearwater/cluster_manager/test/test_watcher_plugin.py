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


from mock import patch
from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import EtcdFactory
import json
from .test_base import BaseClusterTest
from .dummy_plugin import DummyWatcherPlugin
from metaswitch.clearwater.cluster_manager.etcd_synchronizer import \
    EtcdSynchronizer
from time import sleep

class TestWatcherPlugin(BaseClusterTest):

    def setUp(self):
        BaseClusterTest.setUp(self)
        self.watcher_ip = "10.1.1.1"
        self.plugin = DummyWatcherPlugin(self.watcher_ip);

    def tearDown(self):
        self.close_synchronizers()

    @patch("etcd.Client", new=EtcdFactory)
    def test_watcher(self):
        """Create a new 3-node cluster with one plugin not in the cluster and
        check that the main three all end up in NORMAL state"""

        e = self.get_etcd_synchronizer(self.plugin, self.watcher_ip)
        e.start_thread()

        self.make_and_start_synchronizers(3)
        mock_client = self.syncs[0]._client
        self.wait_for_all_normal(mock_client, required_number=3)

        # Pause for one second - the watcher plugin might be called just after
        # all other nodes enter 'normal' state
        sleep(1)
        self.assertTrue(self.plugin.on_stable_cluster_called)

        end = json.loads(mock_client.read("/test").value)
        self.assertEqual("normal", end.get("10.0.0.0"))
        self.assertEqual("normal", end.get("10.0.0.1"))
        self.assertEqual("normal", end.get("10.0.0.2"))
        self.assertEqual(None, end.get("10.1.1.1"))

        e.terminate()

    @patch("etcd.Client")
    def test_leaving(self, client):
        """Create a plugin not in the cluster and try to leave the cluster.
        Nothing should be written to etcd."""
        e = self.get_etcd_synchronizer(self.plugin, self.watcher_ip)
        e.start_thread()

        e.leave_cluster()
        e._client.write.assert_not_called()

        e.terminate()

    @patch("etcd.Client")
    def test_mark_failed(self, client):
        """Create a plugin not in the cluster and try to mark it as failed.
        Nothing should be written to etcd."""
        e = self.get_etcd_synchronizer(self.plugin, self.watcher_ip)
        e.start_thread()

        e.mark_node_failed()
        e._client.write.assert_not_called()

        e.terminate()

