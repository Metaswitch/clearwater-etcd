# @file test_apply_config_plugin.py.py
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

_log = logging.getLogger()

from clearwater_etcd_plugins.clearwater_queue_manager.apply_config_plugin import ApplyConfigPlugin
from metaswitch.clearwater.queue_manager.plugin_base import PluginParams

# run_command returns 0 if the shell command provided succeeds, and the return
# code if it fails. This pair of functions are used as mock side-effects to
# simulate run_command("check_node_health.py") succeeding ir failing.
# The success function is not strictly necessary, but ensures symmetry.

def run_commands_all_succeed(command, **kwargs):
    return 0

def run_commands_check_node_health_fails(command, **kwargs):
    if (command[0] == \
            ["/usr/share/clearwater/clearwater-queue-manager/scripts/check_node_health.py"]):
        return 1
    else:
        return 0

mock_run_commands_success = mock.MagicMock(side_effect=run_commands_all_succeed)
mock_run_commands_unhealthy = mock.MagicMock(side_effect=run_commands_check_node_health_fails)

mock_subproc_check_output = mock.MagicMock()
mock_subproc_check_output.return_value = "apply_config_key"

mock_os_path_exists = mock.MagicMock()
mock_os_listdir = mock.MagicMock()
mock_os_path_exists.return_value = True
mock_os_listdir.return_value = ["test_restart_script", "test_restart_script2"]

PLUGIN_MODULE = "clearwater_etcd_plugins.clearwater_queue_manager.apply_config_plugin"

class TestApplyConfigPlugin(unittest.TestCase):
    def setUp(self):
        mock_os_path_exists.reset_mock()
        mock_os_listdir.reset_mock()
        mock_run_commands_success.reset_mock()
        mock_run_commands_unhealthy.reset_mock()


    @mock.patch(PLUGIN_MODULE + '.subprocess.check_output', new=mock_subproc_check_output)
    @mock.patch(PLUGIN_MODULE + '.os.path.exists', new=mock_os_path_exists)
    @mock.patch(PLUGIN_MODULE + '.os.listdir', new=mock_os_listdir)
    @mock.patch(PLUGIN_MODULE + '.run_commands', new=mock_run_commands_success)
    @mock.patch('metaswitch.clearwater.etcd_shared.plugin_utils.run_commands', new=mock_run_commands_success)
    def test_front_of_queue(self):
        # Create the plugin, and tell it we're at the front of the restart queue.
        plugin = ApplyConfigPlugin(PluginParams(wait_plugin_complete='Y'))
        plugin.at_front_of_queue()

        # The plugin will look for the restart scripts directory, and
        # mock_os_path_exists and mock_os_listdir tell it there are two
        # scripts.
        mock_os_path_exists.assert_called_once_with\
                            ("/usr/share/clearwater/infrastructure/scripts/restart/")
        mock_os_listdir.assert_called_once_with\
                            ("/usr/share/clearwater/infrastructure/scripts/restart/")

        expected_commands = []

        # It then restarts clearwater-infrastructure
        expected_commands.append([['service', 'clearwater-infrastructure', 'restart']])

        # It then runs all the restart scripts in parallel
        expected_commands.append([
            ['/usr/share/clearwater/infrastructure/scripts/restart/test_restart_script'],
            ['/usr/share/clearwater/infrastructure/scripts/restart/test_restart_script2']])

        # It then checks the health of the node - mock_run_commands_success tells us it is healthy
        expected_commands.append([['/usr/share/clearwater/clearwater-queue-manager/scripts/check_node_health.py']])

        # Lastly, it reports success
        expected_commands.append([['/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue', \
                                   'remove_success', 'apply_config_key']])

        expected_command_call_list = [mock.call(x) for x in expected_commands]
        mock_run_commands_success.assert_has_calls(expected_command_call_list)


    @mock.patch(PLUGIN_MODULE + '.subprocess.check_output', new=mock_subproc_check_output)
    @mock.patch(PLUGIN_MODULE + '.os.path.exists', new=mock_os_path_exists)
    @mock.patch(PLUGIN_MODULE + '.os.listdir', new=mock_os_listdir)
    @mock.patch(PLUGIN_MODULE + '.run_commands', new=mock_run_commands_unhealthy)
    @mock.patch('metaswitch.clearwater.etcd_shared.plugin_utils.run_commands', new=mock_run_commands_unhealthy)
    def test_front_of_queue_fail_node_health(self):
        # Create the plugin, and tell it we're at the front of the restart queue.
        plugin = ApplyConfigPlugin(PluginParams(wait_plugin_complete='Y'))
        plugin.at_front_of_queue()

        # The plugin will look for the restart scripts directory, and
        # mock_os_path_exists and mock_os_listdir tell it there are two
        # scripts.
        mock_os_path_exists.assert_called_once_with\
                            ("/usr/share/clearwater/infrastructure/scripts/restart/")
        mock_os_listdir.assert_called_once_with\
                            ("/usr/share/clearwater/infrastructure/scripts/restart/")

        expected_commands = []

        # It then restarts clearwater-infrastructure
        expected_commands.append([['service', 'clearwater-infrastructure', 'restart']])

        # It then runs all the restart scripts in parallel
        expected_commands.append([
            ['/usr/share/clearwater/infrastructure/scripts/restart/test_restart_script'],
            ['/usr/share/clearwater/infrastructure/scripts/restart/test_restart_script2']])

        # It then checks the health of the node - mock_run_commands_unhealthy simulates a failure here
        expected_commands.append([['/usr/share/clearwater/clearwater-queue-manager/scripts/check_node_health.py']])

        # Therefore, it reports failure
        expected_commands.append([['/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue', \
                                   'remove_failure', 'apply_config_key']])

        expected_command_call_list = [mock.call(x) for x in expected_commands]
        mock_run_commands_unhealthy.assert_has_calls(expected_command_call_list)


    @mock.patch(PLUGIN_MODULE + '.subprocess.check_output', new=mock_subproc_check_output)
    @mock.patch(PLUGIN_MODULE + '.os.path.exists', new=mock_os_path_exists)
    @mock.patch(PLUGIN_MODULE + '.os.listdir', new=mock_os_listdir)
    @mock.patch(PLUGIN_MODULE + '.run_commands', new=mock_run_commands_success)
    @mock.patch('metaswitch.clearwater.etcd_shared.plugin_utils.run_commands', new=mock_run_commands_success)
    def test_front_of_queue_no_health_check(self):
        # Create the plugin, and tell it we're at the front of the restart queue.
        plugin = ApplyConfigPlugin(PluginParams(wait_plugin_complete='N'))
        plugin.at_front_of_queue()

        # The plugin will look for the restart scripts directory, and
        # mock_os_path_exists and mock_os_listdir tell it there are two
        # scripts.
        mock_os_path_exists.assert_called_once_with\
                            ("/usr/share/clearwater/infrastructure/scripts/restart/")
        mock_os_listdir.assert_called_once_with\
                            ("/usr/share/clearwater/infrastructure/scripts/restart/")

        expected_commands = []

        # It then restarts clearwater-infrastructure
        expected_commands.append([['service', 'clearwater-infrastructure', 'restart']])

        # It then runs all the restart scripts in parallel
        expected_commands.append([
            ['/usr/share/clearwater/infrastructure/scripts/restart/test_restart_script'],
            ['/usr/share/clearwater/infrastructure/scripts/restart/test_restart_script2']])

        # Because we disabled health checks, it immediately reports success
        expected_commands.append([['/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue', \
                                   'remove_success', 'apply_config_key']])

        expected_command_call_list = [mock.call(x) for x in expected_commands]
        mock_run_commands_success.assert_has_calls(expected_command_call_list)
