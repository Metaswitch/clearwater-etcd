# @file test_chronos_shared_config_plugin.py
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

from clearwater_etcd_plugins.chronos.chronos_shared_config_plugin import ChronosSharedConfigPlugin

class TestConfigManagerPlugin(unittest.TestCase):
    @mock.patch("metaswitch.clearwater.config_manager.alarms.ConfigAlarm")
    @mock.patch('clearwater_etcd_plugins.chronos.chronos_shared_config_plugin.safely_write')
    @mock.patch('clearwater_etcd_plugins.chronos.chronos_shared_config_plugin.run_command')
    def test_chronos_shared_config_changed(self, mock_run_command, mock_safely_write, mock_alarm):
        """Test Chronos shared config plugin writes new config when config has changed"""

        # Create the plugin
        plugin = ChronosSharedConfigPlugin({})

        # Set up the config strings to be tested
        old_config_string = "Old Chronos shared config"
        new_config_string = "New Chronos shared config"

        # Call 'on_config_changed' with file.open mocked out
        with mock.patch('clearwater_etcd_plugins.chronos.chronos_shared_config_plugin.open', \
             mock.mock_open(read_data=old_config_string), create=True) as mock_open:
            plugin.on_config_changed(new_config_string, mock_alarm)

        # Test assertions
        mock_open.assert_called_once_with(plugin.file(), "r")
        mock_safely_write.assert_called_once_with(plugin.file(), new_config_string)
        mock_run_command.assert_called_once_with("/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue add apply_chronos_shared_config")
        mock_alarm.update_file.assert_called_once_with(plugin.file())
