# @file test_queue_manager_plugin.py
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

_log = logging.getLogger()

from clearwater_etcd_plugins.clearwater_queue_manager.apply_config_plugin import ApplyConfigPlugin
from metaswitch.clearwater.cluster_manager.plugin_base import PluginParams

# Helper function to simulate check_node_health failing  
def fail_check_node_health(command):
    if (command == "/usr/share/clearwater/clearwater-queue-manager/scripts/check_node_health.py"):
        return False
    else:
        return True


class TestQueueManagerPlugin(unittest.TestCase):
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.apply_config_plugin.run_command')
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.apply_config_plugin.os.path.exists')
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.apply_config_plugin.os.listdir')
    def test_front_of_queue(self, mock_os_listdir, mock_os_path_exists, mock_run_command):
        """Test Queue Manager front_of_queue function"""

        # Create the plugin
        plugin = ApplyConfigPlugin\
                    (PluginParams(ip='10.0.0.1',
                                  mgmt_ip='10.0.1.1',
                                  local_site='local_site',
                                  remote_site='remote_site',
                                  remote_cassandra_seeds='',
                                  signaling_namespace='',
                                  uuid=uuid.UUID('92a674aa-a64b-4549-b150-596fd466923f'),
                                  etcd_key='etcd_key',
                                  etcd_cluster_key='etcd_cluster_key'))

        # Set up the mock environment and expectations
        mock_os_path_exists.return_value = True
        mock_os_listdir.return_value = ["test_restart_script"]

        expected_command_call_list = \
            [mock.call("service clearwater-infrastructure restart"),
             mock.call("/usr/share/clearwater/infrastructure/scripts/restart/test_restart_script"),
             mock.call("/usr/share/clearwater/clearwater-queue-manager/scripts/check_node_health.py"),
             mock.call().__nonzero__(), # This call comes from the if statement test on the call above
             mock.call("/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue"\
                       " remove_failure apply_config")]

        # Call the plugin hook
        plugin.at_front_of_queue()

        # Test our assertions
        mock_os_path_exists.assert_called_once_with\
                            ("/usr/share/clearwater/infrastructure/scripts/restart")
        mock_os_listdir.assert_called_once_with\
                            ("/usr/share/clearwater/infrastructure/scripts/restart")
        mock_run_command.assert_has_calls(expected_command_call_list)


    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.apply_config_plugin.run_command',\
                side_effect=fail_check_node_health)
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.apply_config_plugin.os.path.exists')
    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.apply_config_plugin.os.listdir')
    def test_front_of_queue_fail_node_health(self, mock_os_listdir,\
                                             mock_os_path_exists, mock_run_command):
        """Test Queue Manager when check_node_health fails"""

        # Create the plugin
        plugin = ApplyConfigPlugin(PluginParams(ip='10.0.0.1',
                                                mgmt_ip='10.0.1.1',
                                                local_site='local_site',
                                                remote_site='remote_site',
                                                remote_cassandra_seeds='',
                                                signaling_namespace='',
                                                uuid=uuid.UUID('92a674aa-a64b-4549-b150-596fd466923f'),
                                                etcd_key='etcd_key',
                                                etcd_cluster_key='etcd_cluster_key'))

        # Set up the mock environment and expectations
        mock_os_path_exists.return_value = True
        mock_os_listdir.return_value = ["test_restart_script"]

        expected_command_call_list = \
            [mock.call("service clearwater-infrastructure restart"),
             mock.call("/usr/share/clearwater/infrastructure/scripts/restart/test_restart_script"),
             mock.call("/usr/share/clearwater/clearwater-queue-manager/scripts/check_node_health.py"),
             mock.call("/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue"\
                       " remove_success apply_config")]

        # Call the plugin hook
        plugin.at_front_of_queue()

        # Test our assertions
        mock_os_path_exists.assert_called_once_with\
                            ("/usr/share/clearwater/infrastructure/scripts/restart")
        mock_os_listdir.assert_called_once_with\
                            ("/usr/share/clearwater/infrastructure/scripts/restart")
        mock_run_command.assert_has_calls(expected_command_call_list)
