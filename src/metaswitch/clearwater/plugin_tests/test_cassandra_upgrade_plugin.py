# @file test_cassandra_upgrade_plugin.py.py
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

from clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin import CassandraUpgradePlugin, UPGRADE_SCRIPT
from metaswitch.clearwater.queue_manager.plugin_base import PluginParams

# run_command returns 0 if the shell command provided succeeds, and the return
# code if it fails. This pair of functions are used as mock side-effects to
# simulate run_command("check_node_health.py") succeeding ir failing.
# The success function is not strictly necessary, but ensures symmetry.

def run_command_all_succeed(command):
    return 0

def run_command_check_node_health_fails(command):
    if (command == "/usr/share/clearwater/clearwater-queue-manager/scripts/check_node_health.py"):
        return 1
    else:
        return 0


class TestCassandraUpgradePlugin(unittest.TestCase):
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin.run_command',\
                side_effect=run_command_all_succeed)
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin.os.path.exists')
    def test_front_of_queue_no_script(self, mock_os_path_exists, mock_run_command):
        """Test Queue Manager front_of_queue function with no upgrade script"""

        # Create the plugin
        plugin = CassandraUpgradePlugin(PluginParams(wait_plugin_complete='Y'))

        # Set up the mock environment and expectations
        mock_os_path_exists.return_value = False

        # If there's no upgrade script, we just remove ourselves from the queue
        expected_command_call_list = \
            [mock.call("/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue"\
                       " remove_success cassandra_upgrade")]

        # Call the plugin hook
        plugin.at_front_of_queue()

        # Test our assertions
        mock_os_path_exists.assert_called_once_with(UPGRADE_SCRIPT)
        mock_run_command.assert_has_calls(expected_command_call_list)


    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin.run_command',\
                side_effect=run_command_all_succeed)
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin.os.path.exists')
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin.imp.load_source')
    def test_front_of_queue(self, mock_imp_load_source, mock_os_path_exists, mock_run_command):
        """Test Queue Manager front_of_queue function with upgrade script"""

        # Create the plugin
        plugin = CassandraUpgradePlugin(PluginParams(wait_plugin_complete='Y'))

        # Set up the mock environment and expectations
        mock_os_path_exists.return_value = True
        mock_cass_upgrade = mock.Mock()
        mock_cass_upgrade.do_upgrade.return_value = True
        mock_imp_load_source.return_value = mock_cass_upgrade

        expected_command_call_list = \
            [mock.call("/usr/share/clearwater/clearwater-queue-manager/scripts/check_node_health.py"),
             mock.call("/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue"\
                       " remove_success cassandra_upgrade")]

        # Call the plugin hook
        plugin.at_front_of_queue()

        # Test our assertions
        mock_os_path_exists.assert_called_once_with(UPGRADE_SCRIPT)
        mock_imp_load_source.assert_called_once_with("cass_upgrade", UPGRADE_SCRIPT)
        mock_cass_upgrade.do_upgrade.assert_called_once_with()
        mock_run_command.assert_has_calls(expected_command_call_list)


    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin.run_command',\
                side_effect=run_command_all_succeed)
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin.os.path.exists')
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin.imp.load_source')
    def test_front_of_queue_upgrade_failed(self, mock_imp_load_source, mock_os_path_exists, mock_run_command):
        """Test Queue Manager front_of_queue function with failed upgrade"""

        # Create the plugin
        plugin = CassandraUpgradePlugin(PluginParams(wait_plugin_complete='Y'))

        # Set up the mock environment and expectations
        mock_os_path_exists.return_value = True
        mock_cass_upgrade = mock.Mock()
        mock_cass_upgrade.do_upgrade.return_value = False
        mock_imp_load_source.return_value = mock_cass_upgrade

        expected_command_call_list = \
            [mock.call("/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue"\
                       " remove_failure cassandra_upgrade")]

        # Call the plugin hook
        plugin.at_front_of_queue()

        # Test our assertions
        mock_os_path_exists.assert_called_once_with(UPGRADE_SCRIPT)
        mock_imp_load_source.assert_called_once_with("cass_upgrade", UPGRADE_SCRIPT)
        mock_cass_upgrade.do_upgrade.assert_called_once_with()
        mock_run_command.assert_has_calls(expected_command_call_list)


    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin.run_command',\
                side_effect=run_command_check_node_health_fails)
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin.os.path.exists')
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin.imp.load_source')
    def test_front_of_queue_fail_node_health(self, mock_imp_load_source, mock_os_path_exists, mock_run_command):
        """Test Queue Manager when check_node_health fails"""

        # Create the plugin
        plugin = CassandraUpgradePlugin(PluginParams(wait_plugin_complete='Y'))

        # Set up the mock environment and expectations
        mock_os_path_exists.return_value = True
        mock_cass_upgrade = mock.Mock()
        mock_cass_upgrade.do_upgrade.return_value = True
        mock_imp_load_source.return_value = mock_cass_upgrade

        expected_command_call_list = \
            [mock.call("/usr/share/clearwater/clearwater-queue-manager/scripts/check_node_health.py"),
             mock.call("/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue"\
                       " remove_failure cassandra_upgrade")]

        # Call the plugin hook
        plugin.at_front_of_queue()

        # Test our assertions
        mock_os_path_exists.assert_called_once_with(UPGRADE_SCRIPT)
        mock_imp_load_source.assert_called_once_with("cass_upgrade", UPGRADE_SCRIPT)
        mock_cass_upgrade.do_upgrade.assert_called_once_with()
        mock_run_command.assert_has_calls(expected_command_call_list)

    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin.run_command',\
                side_effect=run_command_all_succeed)
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin.os.path.exists')
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.cassandra_upgrade_plugin.imp.load_source')
    def test_front_of_queue_no_health_check(self, mock_imp_load_source, mock_os_path_exists, mock_run_command):
        """Test Queue Manager when we're not checking node health"""

        # Create the plugin
        plugin = CassandraUpgradePlugin(PluginParams(wait_plugin_complete='N'))

        # Set up the mock environment and expectations
        mock_os_path_exists.return_value = True
        mock_cass_upgrade = mock.Mock()
        mock_cass_upgrade.do_upgrade.return_value = True
        mock_imp_load_source.return_value = mock_cass_upgrade

        expected_command_call_list = \
            [mock.call("/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue"\
                       " remove_success cassandra_upgrade")]

        # Call the plugin hook
        plugin.at_front_of_queue()

        # Test our assertions
        mock_os_path_exists.assert_called_once_with(UPGRADE_SCRIPT)
        mock_imp_load_source.assert_called_once_with("cass_upgrade", UPGRADE_SCRIPT)
        mock_cass_upgrade.do_upgrade.assert_called_once_with()
        mock_run_command.assert_has_calls(expected_command_call_list)
