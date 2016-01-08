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

from time import sleep
import logging
import sys
import unittest
import json
import os
from functools import partial
from metaswitch.clearwater.etcd_tests.etcdcluster import EtcdCluster
from ..etcd_synchronizer import EtcdSynchronizer
from plugin import TestFVPlugin

logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))
logging.getLogger().setLevel(logging.INFO)

def wait_for_success_or_fail(sync, pass_criteria):
    for x in range(300):
        val = json.loads(sync._client.read("/clearwater/site1/configuration/queue_test").value)
        if pass_criteria(val):
            return True
        sleep(1)
    print "Queue config not updated as expected, final value was: ", val
    return False

def is_queue_config_as_expected(errors, queue, val):
    return (errors == len(val.get("ERRORED"))) and \
           (0 == len(val.get("COMPLETED"))) and \
           (queue == len(val.get("QUEUED")))

class QueueManagerTestBase(unittest.TestCase):
    def tearDown(self):
        for sync in self.syncs:
            sync.terminate()
        sleep(5)
        self.c.delete_datadir()

    def create_synchronizers(self, count):
        self.c = EtcdCluster(count)

        self.syncs = []
        self.plugins = []

        # Create a synchronizer for each node
        x = 0
        for ip in self.c.servers.values():
            self.plugins.append(TestFVPlugin())
            self.syncs.append(EtcdSynchronizer(self.plugins[x], ip._ip, 'site1', 'clearwater', 'nodetype%s' % x))
            self.syncs[x].start_thread()
            x += 1

        sleep(10)
        # Create another synchronizer to act like modify_nodes_in_queue
        self.dummy_sync = EtcdSynchronizer(self.plugins[0], ip._ip, 'site1', 'clearwater', 'nodetypedummy')

    def add_all_nodes_to_queue(self, force):
        queue_list = ""
        for node in self.syncs:
            queue_list += "{\"ID\":\"%s\",\"STATUS\":\"QUEUED\"}," % node._id
        self.dummy_sync._client.write("/clearwater/site1/configuration/queue_test", "{\"FORCE\": " + force + ", \"ERRORED\": [], \"COMPLETED\": [], \"QUEUED\": [" + queue_list[:-1] + "]}")

    # Test that a two node queue is processed appropriately
    @unittest.skipUnless(os.environ.get("SLOW"), "SLOW=T not set")
    def dtest_two_node_queue(self):
        self.create_synchronizers(2)
        
        # Set up the plugins
        self.plugins[0].set_front_of_queue_callback(partial(self.dummy_sync.remove_from_queue, True, self.syncs[0]._id))
        self.plugins[1].set_front_of_queue_callback(partial(self.dummy_sync.remove_from_queue, True, self.syncs[1]._id))
        self.assertFalse(self.plugins[0].at_front_of_queue_called)
        self.assertFalse(self.plugins[1].at_front_of_queue_called)

        # Add nodes to queue
        self.add_all_nodes_to_queue("false")

        # Check output
        self.assertTrue(wait_for_success_or_fail(self.dummy_sync, partial(is_queue_config_as_expected, 0, 0)))
        self.assertTrue(self.plugins[0].at_front_of_queue_called)
        self.assertTrue(self.plugins[1].at_front_of_queue_called)

    # Test that a twenty node queue is processed appropriately
    @unittest.skipUnless(os.environ.get("SLOW"), "SLOW=T not set")
    def test_twenty_node_queue(self):
        self.create_synchronizers(20)

        # Set up the plugins
        for count in range(20):
            self.plugins[count].set_front_of_queue_callback(partial(self.dummy_sync.remove_from_queue, True, self.syncs[count]._id))
            self.assertFalse(self.plugins[count].at_front_of_queue_called)

        # Add nodes to queue
        self.add_all_nodes_to_queue("false")

        # Check output
        self.assertTrue(wait_for_success_or_fail(self.dummy_sync, partial(is_queue_config_as_expected, 0 , 0)))
        for plugin in self.plugins:
            self.assertTrue(plugin.at_front_of_queue_called)

    # Test that a twenty node queue where every node is marked as failed is
    # processed appropriately
    @unittest.skipUnless(os.environ.get("SLOW"), "SLOW=T not set")
    def test_twenty_node_queue_force_true(self):
        self.create_synchronizers(20)

        # Set up the plugins
        for count in range(20):
            self.plugins[count].set_front_of_queue_callback(partial(self.dummy_sync.remove_from_queue, False, self.syncs[count]._id))
            self.assertFalse(self.plugins[count].at_front_of_queue_called)

        # Add nodes to queue
        self.add_all_nodes_to_queue("true")

        # Check output
        self.assertTrue(wait_for_success_or_fail(self.dummy_sync, partial(is_queue_config_as_expected, 20, 0)))
        for plugin in self.plugins:
            self.assertTrue(plugin.at_front_of_queue_called)

    # Test that a two node queue where every node fails aborts after the first failure if
    # force is false
    @unittest.skipUnless(os.environ.get("SLOW"), "SLOW=T not set")
    def test_two_node_queue_force_false(self):
        self.create_synchronizers(2)

        # Set up the plugins
        for count in range(2):
            self.plugins[count].set_front_of_queue_callback(partial(self.dummy_sync.remove_from_queue, False, self.syncs[count]._id))
            self.assertFalse(self.plugins[count].at_front_of_queue_called)

        # Add nodes to queue
        self.add_all_nodes_to_queue("false")

        # Check output
        self.assertTrue(wait_for_success_or_fail(self.dummy_sync, partial(is_queue_config_as_expected, 1, 0)))
        self.assertTrue(self.plugins[0].at_front_of_queue_called)
        self.assertFalse(self.plugins[1].at_front_of_queue_called)
