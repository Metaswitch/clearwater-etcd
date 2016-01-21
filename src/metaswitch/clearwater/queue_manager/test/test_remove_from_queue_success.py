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
from mock import patch, MagicMock
from time import sleep
import json

alarms_patch = patch("metaswitch.clearwater.queue_manager.alarms.issue_alarm", new=MagicMock)

class RemoveFromQueueSuccessTest(BaseQueueTest):
    @patch("etcd.Client", new=EtcdFactory)
    def setUp(self):
        alarms_patch.start()
        self._p = TestPlugin()
        self._e = EtcdSynchronizer(self._p, "10.0.0.1", "local", "clearwater", "node")
        self._e.WAIT_FOR_TIMER_POP = 0

    def remove_from_queue_helper(self):
        success = False

        for x in range(10):
            if self._e.remove_from_queue(True) == WriteToEtcdStatus.SUCCESS:
                success = True
                break
            sleep(1)

        if not success:
            print "Failed to successfully remove the node from the queue"

    # Test that marking a node as successful moves it to the COMPLETED list
    @patch("etcd.Client", new=EtcdFactory)
    def test_remove_from_queue_success(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"}, {\"ID\":\"10.0.0.2-node\",\"STATUS\":\"QUEUED\"}]}")
        self.remove_from_queue_helper()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(0, len(val.get("ERRORED")))
        self.assertEqual(1, len(val.get("COMPLETED")))
        self.assertEqual(1, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.1-node", val.get("COMPLETED")[0]["ID"])
        self.assertEqual("DONE", val.get("COMPLETED")[0]["STATUS"])

    # Test that marking a node as successful when it is still in the queue doesn't move it to the COMPLETED list (but does take out the first entry)
    @patch("etcd.Client", new=EtcdFactory)
    def test_remove_from_queue_success_still_in_queue(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"},{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"QUEUED\"}]}")
        self.remove_from_queue_helper()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(0, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(1, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.1-node", val.get("QUEUED")[0]["ID"])

    # Test that calling this method when the node isn't at the front of the
    # doesn't change the queue
    @patch("etcd.Client", new=EtcdFactory)
    def test_remove_from_queue_success_not_front_of_queue(self):
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"UNRESPONSIVE\"}], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.2-node\",\"STATUS\":\"PROCESSING\"}]}")
        self.remove_from_queue_helper()

        val = json.loads(self._e._client.read("/clearwater/local/configuration/queue_test").value)
        self.assertEqual(1, len(val.get("ERRORED")))
        self.assertEqual(0, len(val.get("COMPLETED")))
        self.assertEqual(1, len(val.get("QUEUED")))
        self.assertEqual("10.0.0.2-node", val.get("QUEUED")[0]["ID"])
        self.assertEqual("PROCESSING", val.get("QUEUED")[0]["STATUS"])
