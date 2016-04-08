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

from .test_base import BaseQueueTest
from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import EtcdFactory
from metaswitch.clearwater.queue_manager.etcd_synchronizer import EtcdSynchronizer, WriteToEtcdStatus
from .plugin import TestPlugin
from mock import patch
from time import sleep
import json

alarms_patch = patch("metaswitch.clearwater.queue_manager.alarms.alarm_manager")

class AddToQueueTest(BaseQueueTest):
    @patch("etcd.Client", new=EtcdFactory)
    def setUp(self):
        alarms_patch.start()
        self._p = TestPlugin()
        self._e = EtcdSynchronizer(self._p, "10.0.0.1", "local", "clearwater", "node")
        self._e.WAIT_FOR_TIMER_POP = 0

    def add_to_queue(self):
        success = False

        for x in range(10):
            if self._e.add_to_queue() == WriteToEtcdStatus.SUCCESS:
                success = True
                break
            sleep(1)

        if not success:
            print "Failed to successfully add the node to the queue"

    # Test that adding to an empty queue simply adds the new node to the QUEUED array
    @patch("etcd.Client", new=EtcdFactory)
    def test_add_to_empty_queue(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": []}")
        self.add_to_queue()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(0, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(1, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[0]["ID"])

    # Test that adding a node when its already in the queue in the processing state adds the new node to the QUEUED array
    @patch("etcd.Client", new=EtcdFactory)
    def test_add_to_queue_already_processing(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"}]}")
        self.add_to_queue()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(0, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(2, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[0]["ID"])
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[1]["ID"])
        self.assertEqual("QUEUED", val.get("QUEUED")[1]["STATUS"])

    # Test that adding a node when its already in the queue in the queued state doesn't add the new node to the QUEUED array
    @patch("etcd.Client", new=EtcdFactory)
    def test_add_to_queue_already_queued(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"}, {\"ID\":\"10.0.0.1-node\",\"STATUS\":\"QUEUED\"}]}")
        self.add_to_queue()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(0, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(2, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[0]["ID"])
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[1]["ID"])
        self.assertEqual("QUEUED", val.get("QUEUED")[1]["STATUS"])

    # Test that adding a node when its not already in the queue in the queued state adds the node (with more nodes in the queue already)
    @patch("etcd.Client", new=EtcdFactory)
    def test_add_to_queue_with_other_nodes_and_already_queued(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"}, {\"ID\":\"10.0.0.2-node\",\"STATUS\":\"QUEUED\"}]}")
        self.add_to_queue()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(0, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(3, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[0]["ID"])
        self.assertEqual("10.0.0.2-node", val.get("QUEUED")[1]["ID"])
        self.assertEqual("QUEUED", val.get("QUEUED")[1]["STATUS"])
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[2]["ID"])
        self.assertEqual("QUEUED", val.get("QUEUED")[2]["STATUS"])

    # Test that adding the node succeeds for a non-empty queue that its not already in
    @patch("etcd.Client", new=EtcdFactory)
    def test_add_to_queue_with_other_nodes(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.2-node\",\"STATUS\":\"PROCESSING\"}]}")
        self.add_to_queue()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(0, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(2, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.2-node", val.get("QUEUED")[0]["ID"])
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[1]["ID"])
        self.assertEqual("QUEUED", val.get("QUEUED")[1]["STATUS"])

    # Test that adding a node to an empty queue with an unresponsive node doesn't add the unresponsive node to the queue
    @patch("etcd.Client", new=EtcdFactory)
    def test_add_to_empty_queue_and_other_node_unresponsive(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [{\"ID\":\"10.0.0.2-node\",\"STATUS\":\"UNRESPONSIVE\"}], \"COMPLETED\": [], \"QUEUED\": []}")
        self.add_to_queue()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(0, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(1, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[0]["ID"])

    # Test that adding a node to an empty queue with an failed node adds the failed node to the front of the queue
    @patch("etcd.Client", new=EtcdFactory)
    def test_add_to_empty_queue_and_other_node_failed(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [{\"ID\":\"10.0.0.2-node\",\"STATUS\":\"FAILURE\"}], \"COMPLETED\": [], \"QUEUED\": []}")
        self.add_to_queue()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(0, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(2, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.2-node", val.get("QUEUED")[0]["ID"])
        self.assertEqual("QUEUED", val.get("QUEUED")[0]["STATUS"])
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[1]["ID"])
        self.assertEqual("QUEUED", val.get("QUEUED")[1]["STATUS"])

    # Test that adding a node to an empty queue with this node marked as failed node only adds the node to the queue once
    @patch("etcd.Client", new=EtcdFactory)
    def test_add_to_empty_queue_and_this_node_failed(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"FAILURE\"}], \"COMPLETED\": [], \"QUEUED\": []}")
        self.add_to_queue()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(0, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(1, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[0]["ID"])

    # Test that adding a node when it's marked as completed removes the node from the completed list
    @patch("etcd.Client", new=EtcdFactory)
    def test_add_to_queue_while_completed(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"DONE\"}], \"QUEUED\": [{\"ID\":\"10.0.0.2-node\",\"STATUS\":\"PROCESSING\"}]}")
        self.add_to_queue()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(0, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(2, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.2-node", val.get("QUEUED")[0]["ID"])
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[1]["ID"])
        self.assertEqual("QUEUED", val.get("QUEUED")[1]["STATUS"])

    # Test that adding a node that's marked as errored when it's not at the front of the queue doesn't change the errored state
    @patch("etcd.Client", new=EtcdFactory)
    def test_add_to_queue_while_errored(self):
        self.set_initial_val("{\"FORCE\": true, \"ERRORED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"FAILURE\"}], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.2-node\",\"STATUS\":\"PROCESSING\"}]}")
        self.add_to_queue()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(1, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(2, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.2-node", val.get("QUEUED")[0]["ID"])
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[1]["ID"])
        self.assertEqual("QUEUED", val.get("QUEUED")[1]["STATUS"])
