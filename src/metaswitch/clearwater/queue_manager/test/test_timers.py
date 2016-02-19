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

from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import EtcdFactory
from metaswitch.clearwater.queue_manager.etcd_synchronizer import EtcdSynchronizer
from .plugin import TestNoTimerDelayPlugin
from mock import patch, MagicMock
from .test_base import BaseQueueTest

alarms_patch = patch("metaswitch.clearwater.queue_manager.alarms.alarm_manager")

class TimersTest(BaseQueueTest):
    @patch("etcd.Client", new=EtcdFactory)
    def setUp(self):
        alarms_patch.start()
        self._p = TestNoTimerDelayPlugin()
        self._e = EtcdSynchronizer(self._p, "10.0.0.1", "local", "clearwater", "node")

    # Test that when a timer pops for the current node it marks the node as failed
    def test_this_node_timer_pop(self):
        # Write some initial data into the key
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"}]}")

        def pass_criteria(val):
            return (1 == len(val.get("ERRORED"))) and \
                   (0 == len(val.get("COMPLETED"))) and \
                   (0 == len(val.get("QUEUED"))) and \
                   ("10.0.0.1-node" == val.get("ERRORED")[0]["ID"]) and \
                   ("UNRESPONSIVE" == val.get("ERRORED")[0]["STATUS"])

        self.assertTrue(self.wait_for_success_or_fail(pass_criteria))

    @patch("etcd.Client", new=EtcdFactory)
    # Test that when a timer pops for another node it marks the other node as failed
    def test_other_node_timer_pop(self):
        # Write some initial data into the key
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.2-node\",\"STATUS\":\"PROCESSING\"}]}")

        def pass_criteria(val):
            return (1 == len(val.get("ERRORED"))) and \
                   (0 == len(val.get("COMPLETED"))) and \
                   (0 == len(val.get("QUEUED"))) and \
                   ("10.0.0.2-node" == val.get("ERRORED")[0]["ID"]) and \
                   ("UNRESPONSIVE" == val.get("ERRORED")[0]["STATUS"])

        self.assertTrue(self.wait_for_success_or_fail(pass_criteria))

    # Test that when a timer pops when force is true it doesn't clear the queue
    def test_timer_pop_force(self):
        # Write some initial data into the key
        self.set_initial_val("{\"FORCE\": true, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"},{\"ID\":\"10.0.0.2-node\",\"STATUS\":\"QUEUED\"}]}")

        def pass_criteria(val):
            return (2 == len(val.get("ERRORED"))) and \
                   (0 == len(val.get("COMPLETED"))) and \
                   (0 == len(val.get("QUEUED"))) and \
                   ("10.0.0.1-node" == val.get("ERRORED")[0]["ID"]) and \
                   ("UNRESPONSIVE" == val.get("ERRORED")[0]["STATUS"]) and \
                   ("10.0.0.2-node" == val.get("ERRORED")[1]["ID"]) and \
                   ("UNRESPONSIVE" == val.get("ERRORED")[1]["STATUS"])

        self.assertTrue(self.wait_for_success_or_fail(pass_criteria))

    # Test that when a timer pops when force is false it does clear the queue
    def test_timer_pop_no_force(self):
        # Write some initial data into the key
        self.set_initial_val("{\"FORCE\": false, \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [{\"ID\":\"10.0.0.1-node\",\"STATUS\":\"PROCESSING\"},{\"ID\":\"10.0.0.2-node\",\"STATUS\":\"PROCESSING\"}]}")

        def pass_criteria(val):
            return (1 == len(val.get("ERRORED"))) and \
                   (0 == len(val.get("COMPLETED"))) and \
                   (0 == len(val.get("QUEUED"))) and \
                   ("10.0.0.1-node" == val.get("ERRORED")[0]["ID"]) and \
                   ("UNRESPONSIVE" == val.get("ERRORED")[0]["STATUS"])

        self.assertTrue(self.wait_for_success_or_fail(pass_criteria))
