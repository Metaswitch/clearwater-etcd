# @file test_cassandra_failed_plugin.py
#
# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import unittest
import mock
import logging

_log = logging.getLogger()

from clearwater_etcd_plugins.clearwater_cassandra.cassandra_failed_plugin import CassandraFailedPlugin

class TestCassandraFailedPlugin(unittest.TestCase):
    # run_command returns 0 if a command completes successfully, but python mocks
    # return 'True', i.e. 1. Force return value of 0 to simulate successes.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_failed_plugin.run_command',\
                return_value=0)
    @mock.patch('metaswitch.common.alarms.alarm_manager.get_alarm')
    # The plugin uses check_output to get the node ID from nodetool status, so mock up a response.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_failed_plugin.subprocess.check_output',\
                return_value="UN  10.0.0.1   177.36 KB  256     100.0%            92a674aa-a64b-4549-b150-596fd466923f  RAC1")
    def test_cassandra_failed_leaving_cluster(self,\
                                              mock_check_output,\
                                              mock_get_alarm,\
                                              mock_run_command):
        """Test the cassandra_failed_plugin leaving cluster process"""

        # Create a plugin with dummy parameters
        plugin = CassandraFailedPlugin(key="etcd_key/etcd_cluster_key/clustering/cassandra",
                                       ip='10.0.0.1')

        # Build a cluster_view that includes all possible node states
        cluster_view = {"10.0.0.1": "normal"}

        plugin.on_leaving_cluster(cluster_view)

        # Check that we remove the corect node ID
        run_command_call_list = \
             [mock.call("/usr/share/clearwater/bin/run-in-signaling-namespace nodetool removenode 92a674aa-a64b-4549-b150-596fd466923f")]

        mock_run_command.assert_has_calls(run_command_call_list)
