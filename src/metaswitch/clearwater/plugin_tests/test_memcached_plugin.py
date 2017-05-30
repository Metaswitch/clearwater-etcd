# @file test_memcached_plugin.py
#
# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import unittest
import mock
import logging
import uuid
from collections import Counter

_log = logging.getLogger()

from clearwater_etcd_plugins.clearwater_memcached.memcached_plugin import MemcachedPlugin
from clearwater_etcd_plugins.clearwater_memcached.memcached_remote_plugin import RemoteMemcachedPlugin
from metaswitch.clearwater.cluster_manager.plugin_base import PluginParams
from metaswitch.clearwater.cluster_manager import alarm_constants


class TestMemcachedPlugin(unittest.TestCase):
    @mock.patch('clearwater_etcd_plugins.clearwater_memcached.memcached_plugin.run_command')
    @mock.patch('clearwater_etcd_plugins.clearwater_memcached.memcached_utils.safely_write')
    @mock.patch('metaswitch.common.alarms.alarm_manager.get_alarm')
    def test_write_config_all_node_states(self, mock_get_alarm, mock_safely_write, mock_run_command):
        """Test memcached_plugin writes settings correctly when given all possible server states"""

        # Create a plugin with dummy parameters
        plugin = MemcachedPlugin(PluginParams(ip='10.0.0.1',
                                              mgmt_ip='10.0.1.1',
                                              local_site='local_site',
                                              remote_site='remote_site',
                                              remote_cassandra_seeds='',
                                              signaling_namespace='',
                                              uuid=uuid.UUID('92a674aa-a64b-4549-b150-596fd466923f'),
                                              etcd_key='etcd_key',
                                              etcd_cluster_key='etcd_cluster_key'))

        # We expect this alarm to be called on creation of the plugin
        mock_get_alarm.assert_called_once_with('cluster-manager',
                                               alarm_constants.MEMCACHED_NOT_YET_CLUSTERED)

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


    @mock.patch('clearwater_etcd_plugins.clearwater_memcached.memcached_plugin.run_command')
    @mock.patch('clearwater_etcd_plugins.clearwater_memcached.memcached_utils.safely_write')
    @mock.patch('metaswitch.common.alarms.alarm_manager.get_alarm')
    def test_write_config_no_server_changes(self, mock_get_alarm, mock_safely_write, mock_run_command):
        """Test memcached_plugin writes settings correctly when servers aren't changing state"""

        # Create a plugin with dummy parameters
        plugin = MemcachedPlugin(PluginParams(ip='10.0.0.1',
                                              mgmt_ip='10.0.1.1',
                                              local_site='local_site',
                                              remote_site='remote_site',
                                              remote_cassandra_seeds='',
                                              signaling_namespace='',
                                              uuid=uuid.UUID('92a674aa-a64b-4549-b150-596fd466923f'),
                                              etcd_key='etcd_key',
                                              etcd_cluster_key='etcd_cluster_key'))

        # We expect this alarm to be called on creation of the plugin
        mock_get_alarm.assert_called_once_with('cluster-manager',
                                               alarm_constants.MEMCACHED_NOT_YET_CLUSTERED)

        # Build a cluster_view that covers all states that would leave
        # current and new servers lists the same
        cluster_view = {"10.0.0.1": "waiting to join",
                        "10.0.0.2": "joining",
                        "10.0.0.5": "normal",
                        "10.0.0.6": "normal, acknowledged change",
                        "10.0.0.7": "normal, config changed",
                        "10.0.0.8": "waiting to leave",
                        "10.0.0.9": "leaving",
                        "10.0.0.12": "finished",
                        "10.0.0.13": "error"}

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

        # Assert there is no 'new_servers' line
        new_server_list = [s for s in config_lines if s.startswith('new_servers')]
        self.assertTrue(len(new_server_list) == 0)

        # Set expectations, and assert that the correct ips made it into servers list
        expected_server_ips = Counter(['10.0.0.5', '10.0.0.6', '10.0.0.7'])
        self.assertTrue(server_ips == expected_server_ips)


    @mock.patch('clearwater_etcd_plugins.clearwater_memcached.memcached_remote_plugin.run_command')
    @mock.patch('clearwater_etcd_plugins.clearwater_memcached.memcached_utils.safely_write')
    def test_remote_plugin_write_config(self, mock_safely_write, mock_run_command):
        """Test remote_memcached_plugin writes settings correctly"""

        # Create a plugin with dummy parameters
        plugin = RemoteMemcachedPlugin(PluginParams(ip='10.0.0.1',
                                                    mgmt_ip='10.0.1.1',
                                                    local_site='local_site',
                                                    remote_site='remote_site',
                                                    remote_cassandra_seeds='',
                                                    signaling_namespace='',
                                                    uuid=uuid.UUID('92a674aa-a64b-4549-b150-596fd466923f'),
                                                    etcd_key='etcd_key',
                                                    etcd_cluster_key='etcd_cluster_key'))

        # Config writing is properly tested above, so run with simple cluster
        cluster_view = {"10.0.0.5": "normal"}

        # Call the plugin to write the settings itself
        plugin.write_cluster_settings(cluster_view)
        mock_safely_write.assert_called_once()
        # Save off the arguments the plugin called our mock with
        args = mock_safely_write.call_args

        # Catch the call to reload memcached
        mock_run_command.assert_called_once_with("/usr/share/clearwater/bin/reload_memcached_users")

        # Check the plugin is attempting to write to the correct location
        self.assertEqual("/etc/clearwater/remote_cluster_settings", args[0][0])
