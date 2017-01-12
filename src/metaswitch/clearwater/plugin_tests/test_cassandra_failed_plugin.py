# @file test_cassandra_failed_plugin.py
#
# Project Clearwater - IMS in the Cloud
# Copyright (C) 2016 Metaswitch Networks Ltd
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
