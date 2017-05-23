# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

from time import sleep
import unittest
import json
import os
from functools import partial
from metaswitch.clearwater.etcd_tests.etcdcluster import EtcdCluster
from ..etcd_synchronizer import EtcdSynchronizer
from plugin import TestFVPlugin


def wait_for_success_or_fail(sync, pass_criteria):
    for x in range(300):
        val = json.loads(sync._client.read("/clearwater/site1/configuration/queue_test").value)
        if pass_criteria(val):
            return True
        sleep(1)
    print "Queue config not updated as expected, final value was: ", val
    return False

def is_queue_config_as_expected(errors, queue, val):
    try:
        return (errors == len(val.get("ERRORED"))) and \
               (0 == len(val.get("COMPLETED"))) and \
               (queue == len(val.get("QUEUED")))
    except TypeError:
        print "Queue config has missing JSON values"
        return False

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
        for x, ip in enumerate(self.c.servers.values()):
            self.plugins.append(TestFVPlugin())
            self.syncs.append(EtcdSynchronizer(self.plugins[x], ip._ip, 'site1', 'clearwater', 'nodetype%s' % x))
            self.syncs[x].start_thread()

        sleep(10)

        # Create another synchronizer to act like modify_nodes_in_queue
        self.dummy_sync = EtcdSynchronizer(self.plugins[0], ip._ip, 'site1', 'clearwater', 'nodetypedummy')

    def add_all_nodes_to_queue(self, force):
        queue_dict = json.loads(self.dummy_sync.default_value())
        queue_dict["FORCE"] = force

        for node in self.syncs:
            queue = {}
            queue["ID"] = node._id
            queue["STATUS"] = "QUEUED"
            queue_dict["QUEUED"].append(queue)

        self.dummy_sync._client.write("/clearwater/site1/configuration/queue_test", json.dumps(queue_dict))

    # Test that a two node queue is processed appropriately
    @unittest.skipUnless(os.environ.get("SLOW"), "SLOW=T not set")
    def temp_test_two_node_queue(self):
        self.create_synchronizers(2)
        
        # Set up the plugins
        for p, sync in zip(self.plugins, self.syncs):
            leave = partial(self.dummy_sync.remove_from_queue, False, sync._id)
            p.when_at_front_of_queue(leave)
            self.assertFalse(p.at_front_of_queue_called)

        # Add nodes to queue
        self.add_all_nodes_to_queue(False)

        # Check output - The queue is now empty and each node has been at the front of the queue.
        self.assertTrue(wait_for_success_or_fail(self.dummy_sync, partial(is_queue_config_as_expected, 0, 0)))
        for plugin in self.plugins:
            self.assertTrue(plugin.at_front_of_queue_called)

    # Test that a twenty node queue is processed appropriately
    @unittest.skipUnless(os.environ.get("SLOW"), "SLOW=T not set")
    def temp_test_twenty_node_queue(self):
        self.create_synchronizers(20)

        # Set up the plugins
        for count in range(20):
            self.plugins[count].when_at_front_of_queue(partial(self.dummy_sync.remove_from_queue, True, self.syncs[count]._id))
            self.assertFalse(self.plugins[count].at_front_of_queue_called)

        # Add nodes to queue
        self.add_all_nodes_to_queue(False)

        # Check output - The queue is now empty and each node has been at the front of the queue.
        self.assertTrue(wait_for_success_or_fail(self.dummy_sync, partial(is_queue_config_as_expected, 0 , 0)))
        for plugin in self.plugins:
            self.assertTrue(plugin.at_front_of_queue_called)

    # Test that a twenty node queue where every node is marked as failed is
    # processed appropriately
    @unittest.skipUnless(os.environ.get("SLOW"), "SLOW=T not set")
    def temp_test_twenty_node_queue_force_true(self):
        self.create_synchronizers(20)

        # Set up the plugins
        for count in range(20):
            self.plugins[count].when_at_front_of_queue(partial(self.dummy_sync.remove_from_queue, False, self.syncs[count]._id))
            self.assertFalse(self.plugins[count].at_front_of_queue_called)

        # Add nodes to queue
        self.add_all_nodes_to_queue(True)

        # Check output - all nodes are errored, all nodes reached the front of the queue
        self.assertTrue(wait_for_success_or_fail(self.dummy_sync, partial(is_queue_config_as_expected, 20, 0)))
        for plugin in self.plugins:
            self.assertTrue(plugin.at_front_of_queue_called)

    # Test that a two node queue where every node fails aborts after the first failure if
    # force is false
    @unittest.skipUnless(os.environ.get("SLOW"), "SLOW=T not set")
    def temp_test_two_node_queue_force_false(self):
        self.create_synchronizers(2)

        # Set up the plugins
        for count in range(2):
            self.plugins[count].when_at_front_of_queue(partial(self.dummy_sync.remove_from_queue, False, self.syncs[count]._id))
            self.assertFalse(self.plugins[count].at_front_of_queue_called)

        # Add nodes to queue
        self.add_all_nodes_to_queue(False)

        # Check output - one node is errored, the queue is empty, and only the errored node reached the front of the queue
        self.assertTrue(wait_for_success_or_fail(self.dummy_sync, partial(is_queue_config_as_expected, 1, 0)))
        self.assertTrue(self.plugins[0].at_front_of_queue_called)
        self.assertFalse(self.plugins[1].at_front_of_queue_called)
