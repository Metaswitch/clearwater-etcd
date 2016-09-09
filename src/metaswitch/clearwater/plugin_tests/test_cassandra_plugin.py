# @file test_cassandra_plugin.py
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
import uuid
from collections import Counter

_log = logging.getLogger()

from clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin import CassandraPlugin
from metaswitch.clearwater.cluster_manager.plugin_base import PluginParams
from metaswitch.clearwater.cluster_manager import alarm_constants


class TestCassandraPlugin(unittest.TestCase):
#    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.run_command')
#    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.safely_write')
    @mock.patch('metaswitch.common.alarms.alarm_manager.get_alarm')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.path.exists')
#    def test_cassandra_startup(self, mock_os_path, mock_get_alarm, mock_safely_write, mock_run_command):
    def test_cassandra_startup(self, mock_os_path, mock_get_alarm):
        """Test the cassandra_plugin startup and joining process"""

        # Create a plugin with dummy parameters
        plugin = CassandraPlugin(PluginParams(ip='10.0.0.1',
                                              mgmt_ip='10.0.1.1',
                                              local_site='local_site',
                                              remote_site='remote_site',
                                              remote_cassandra_seeds='10.2.2.1',
                                              signaling_namespace='',
                                              uuid=uuid.UUID('92a674aa-a64b-4549-b150-596fd466923f'),
                                              etcd_key='etcd_key',
                                              etcd_cluster_key='etcd_cluster_key'))

        # We expect this alarm to be called on creation of the plugin
        mock_get_alarm.assert_called_once_with('cluster-manager',
                                               alarm_constants.CASSANDRA_NOT_YET_CLUSTERED)

        # Build a cluster_view that includes all possible node states
        cluster_view = {"10.0.0.1": "waiting to join",
                        "10.0.0.2": "joining",
                        "10.0.0.3": "joining, acknowledged change",
                        "10.0.0.4": "joining, config changed",
                        "10.0.0.5": "normal",
                        "10.0.0.6": "normal, acknowledged change",
                        "10.0.0.7": "normal, config changed",
                        "10.0.0.8": "waiting to leave",
                        "10.0.0.9": "leaving",
                        "10.0.0.10": "leaving, acknowledged change",
                        "10.0.0.11": "leaving, config changed",
                        "10.0.0.12": "finished",
                        "10.0.0.13": "error"}

        # Set up conditions
        mock_os_path.return_value = True

        template = "test"

        # Call startup actions, as the FSM would
        with mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.open', mock.mock_open(read_data=template), create=True) as mock_open:
            plugin.on_startup(cluster_view)

        mock_os_path.assert_called_once_with("/etc/clearwater/force_cassandra_yaml_refresh")

"""        
        # Call the plugin to write the settings itself
        plugin.write_cluster_settings(cluster_view)
        mock_safely_write.assert_called_once()
        # Save off the arguments the plugin called our mock with
        args = mock_safely_write.call_args

        # Catch the call to reload memcached
        mock_run_command.assert_called_once_with("/usr/share/clearwater/bin/reload_memcached_users")

        # Check the plugin is attempting to write to the correct location
        self.assertEqual("/etc/clearwater/cluster_settings", args[0][0])

        # Save off the file contents sent to the mock safely_write call
        # The file is not a proper config file structure, so we do string
        # based parsing, rather than using python ConfigParser
        config_string = args[0][1]
        config_lines = config_string.splitlines()

        # Assert there is only one 'servers' line, and parse out the ips.
        server_list = [s for s in config_lines if s.startswith('servers')]
        self.assertTrue(len(server_list) == 1)
        server_ips_with_ports = [s for s in (str(server_list[0]).strip('servers=')).split(',')]
        server_ips = Counter([ip.split(':')[0] for ip in server_ips_with_ports])

        # Assert there is only one 'new_servers' line, and parse out the ips.
        new_server_list = [s for s in config_lines if s.startswith('new_servers')]
        self.assertTrue(len(new_server_list) == 1)
        new_server_ips_with_ports = [s for s in (str(new_server_list[0]).strip('new_servers=')).split(',')]
        new_server_ips = Counter([ip.split(':')[0] for ip in new_server_ips_with_ports])

        # Set expectations, and assert that the correct ips made it into each list
        expected_server_ips = Counter(['10.0.0.5', '10.0.0.6', '10.0.0.7', '10.0.0.10', '10.0.0.11'])
        expected_new_server_ips = Counter(['10.0.0.3', '10.0.0.4', '10.0.0.5', '10.0.0.6', '10.0.0.7'])

        self.assertTrue(server_ips == expected_server_ips)
        self.assertTrue(new_server_ips == expected_new_server_ips)
"""
