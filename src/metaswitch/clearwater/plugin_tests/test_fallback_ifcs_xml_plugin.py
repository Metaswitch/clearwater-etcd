# @file test_fallback_ifcs_xml_plugin.py
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

from clearwater_etcd_plugins.clearwater_config_manager.fallback_ifcs_xml_plugin import FallbackIFCsXMLPlugin

class TestFallbackIFCsXMLPlugin(unittest.TestCase):
    @mock.patch("metaswitch.clearwater.config_manager.alarms.ConfigAlarm")
    @mock.patch('clearwater_etcd_plugins.clearwater_config_manager.fallback_ifcs_xml_plugin.safely_write')
    @mock.patch('clearwater_etcd_plugins.clearwater_config_manager.fallback_ifcs_xml_plugin.run_command')
    def test_config_changed(self, mock_run_command, mock_safely_write, mock_alarm):
        """Test Config Manager writes new config when config has changed"""

        # Create the plugin
        plugin = FallbackIFCsXMLPlugin(None)

        # Set up the config strings to be tested
        old_config_string = "Test config string here. \n More test config string."
        new_config_string = "This is a different config string. \n Like, totally different."

        # Call 'on_config_changed' with file.open mocked out
        with mock.patch('clearwater_etcd_plugins.clearwater_config_manager.fallback_ifcs_xml_plugin.open',\
                        mock.mock_open(read_data=old_config_string), create=True) as mock_open:
            plugin.on_config_changed(new_config_string, mock_alarm)

        # Test assertions
        mock_open.assert_called_once_with(plugin.file(), "r")
        mock_safely_write.assert_called_once_with(plugin.file(), new_config_string)
        mock_run_command.assert_called_once_with(["/usr/share/clearwater/bin/reload_fallback_ifcs_xml"])
        mock_alarm.update_file.assert_called_once_with(plugin.file())


    @mock.patch('clearwater_etcd_plugins.clearwater_config_manager.fallback_ifcs_xml_plugin.safely_write')
    @mock.patch('clearwater_etcd_plugins.clearwater_config_manager.fallback_ifcs_xml_plugin.run_command')
    def test_config_not_changed(self, mock_run_command, mock_safely_write):
        """Test Config Manager does nothing if called with identical config"""

        # Create the plugin
        plugin = FallbackIFCsXMLPlugin(None)

        # Set up the config strings to be tested
        old_config_string = "This is more test config. \n It won't change."
        new_config_string = old_config_string

        # Call 'on_config_changed' with file.open mocked out
        with mock.patch('clearwater_etcd_plugins.clearwater_config_manager.fallback_ifcs_xml_plugin.open',\
                        mock.mock_open(read_data=old_config_string), create=True) as mock_open:
            plugin.on_config_changed(new_config_string, None)

        # Test assertions
        mock_open.assert_called_once_with(plugin.file(), "r")
        mock_safely_write.assert_not_called()
        mock_run_command.assert_not_called()

    @mock.patch("metaswitch.clearwater.config_manager.alarms.ConfigAlarm")
    @mock.patch('clearwater_etcd_plugins.clearwater_config_manager.fallback_ifcs_xml_plugin.safely_write')
    @mock.patch('clearwater_etcd_plugins.clearwater_config_manager.fallback_ifcs_xml_plugin.run_command')
    def test_default_config_created(self, mock_run_command, mock_safely_write, mock_alarm):
        """Test Config Manager writes new config when a new default value is set as etcd key"""

        # Create the plugin
        plugin = FallbackIFCsXMLPlugin(None)

        # Set up the config strings to be tested
        old_config_string = "This is clearly not the default config value."
        new_config_string = plugin.default_value()

        # Call 'on_config_changed' with file.open mocked out
        with mock.patch('clearwater_etcd_plugins.clearwater_config_manager.fallback_ifcs_xml_plugin.open',\
                        mock.mock_open(read_data=old_config_string), create=True) as mock_open:
            plugin.on_config_changed(new_config_string, mock_alarm)

        # Test assertions
        mock_open.assert_called_once_with(plugin.file(), "r")
        mock_safely_write.assert_called_once_with(plugin.file(), plugin.default_value())
        mock_run_command.assert_called_once_with(["/usr/share/clearwater/bin/reload_fallback_ifcs_xml"])
        mock_alarm.update_file.assert_called_once_with(plugin.file())
