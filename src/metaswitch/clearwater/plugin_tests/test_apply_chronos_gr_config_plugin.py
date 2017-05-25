# @file test_apply_chronos_gr_config_plugin.py
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

from clearwater_etcd_plugins.chronos.apply_chronos_gr_config_plugin import ApplyChronosGRConfigPlugin

class TestApplyChronosGRConfigPlugin(unittest.TestCase):
    @mock.patch('clearwater_etcd_plugins.chronos.apply_chronos_gr_config_plugin.run_command')
    def test_front_of_queue(self, mock_run_command):
        """Test apply Chronos GR config plugin front_of_queue function"""

        # Create the plugin
        plugin = ApplyChronosGRConfigPlugin({})

        expected_command_call_list = \
            [mock.call("service chronos stop"),
             mock.call().__nonzero__(),
             mock.call("service chronos wait-sync"),
             mock.call().__nonzero__(),
             mock.call("/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue"\
                       " remove_success apply_chronos_gr_config"),
             mock.call().__nonzero__()]

        # Call the plugin hook
        plugin.at_front_of_queue()

        # Test our assertions
        mock_run_command.assert_has_calls(expected_command_call_list)
