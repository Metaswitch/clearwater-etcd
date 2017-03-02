# @file test_apply_chronos_gr_config_plugin.py
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
