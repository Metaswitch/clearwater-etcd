# @file test_default_ifcs_config_plugin.py
#
# Project Clearwater - IMS in the Cloud
# Copyright (C) 2017 Metaswitch Networks Ltd
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

from clearwater_etcd_plugins.clearwater_config_manager.default_ifcs_config_plugin import DefaultIFCsConfigPlugin


class TestDefaultIFCsConfigPlugin(unittest.TestCase):
    @mock.patch('clearwater_etcd_plugins.clearwater_config_manager.default_ifcs_config_plugin.safely_write')
    @mock.patch('clearwater_etcd_plugins.clearwater_config_manager.default_ifcs_config_plugin.run_command')
    def test_config_changed(self, mock_run_command, mock_safely_write):
        """Test Config Manager writes new config when config has changed"""

        # Create the plugin
        plugin = DefaultIFCsConfigPlugin(None)

        # Set up the config strings to be tested
        old_config_string = "Test config string here. \n More test config string."
        new_config_string = "This is a different config string. \n Like, totally different."

        # Call 'on_config_changed' with file.open mocked out
        with mock.patch('clearwater_etcd_plugins.clearwater_config_manager.default_ifcs_config_plugin.open',\
                        mock.mock_open(read_data=old_config_string), create=True) as mock_open:
            plugin.on_config_changed(new_config_string, None)

        # Test assertions
        mock_open.assert_called_once_with(plugin.file(), "r")
        mock_safely_write.assert_called_once_with(plugin.file(), new_config_string)
        mock_run_command.assert_called_once_with("/usr/share/clearwater/bin/reload_default_ifcs_config")


    @mock.patch('clearwater_etcd_plugins.clearwater_config_manager.default_ifcs_config_plugin.safely_write')
    @mock.patch('clearwater_etcd_plugins.clearwater_config_manager.default_ifcs_config_plugin.run_command')
    def test_config_not_changed(self, mock_run_command, mock_safely_write):
        """Test Config Manager does nothing if called with identical config"""

        # Create the plugin
        plugin = DefaultIFCsConfigPlugin(None)

        # Set up the config strings to be tested
        old_config_string = "This is more test config. \n It won't change."
        new_config_string = old_config_string

        # Call 'on_config_changed' with file.open mocked out
        with mock.patch('clearwater_etcd_plugins.clearwater_config_manager.default_ifcs_config_plugin.open',\
                        mock.mock_open(read_data=old_config_string), create=True) as mock_open:
            plugin.on_config_changed(new_config_string, None)

        # Test assertions
        mock_open.assert_called_once_with(plugin.file(), "r")
        mock_safely_write.assert_not_called()
        mock_run_command.assert_not_called()

    @mock.patch('clearwater_etcd_plugins.clearwater_config_manager.default_ifcs_config_plugin.safely_write')
    @mock.patch('clearwater_etcd_plugins.clearwater_config_manager.default_ifcs_config_plugin.run_command')
    def test_default_config_created(self, mock_run_command, mock_safely_write):
        """Test Config Manager when a new default value is set as etcd key"""

        # Create the plugin
        plugin = DefaultIFCsConfigPlugin(None)

        # Set up the config strings to be tested
        old_config_string = "This is clearly not the default config value."
        new_config_string = plugin.default_value()

        # Call 'on_config_changed' with file.open mocked out
        with mock.patch('clearwater_etcd_plugins.clearwater_config_manager.default_ifcs_config_plugin.open',\
                        mock.mock_open(read_data=old_config_string), create=True) as mock_open:
            plugin.on_config_changed(new_config_string, None)

        # Test assertions
        mock_open.assert_called_once_with(plugin.file(), "r")
        mock_safely_write.assert_called_once_with(plugin.file(), plugin.default_value())
        mock_run_command.assert_called_once_with("/usr/share/clearwater/bin/reload_default_ifcs_config")
