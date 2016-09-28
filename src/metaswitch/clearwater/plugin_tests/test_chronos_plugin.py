# @file test_chronos_plugin.py
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
from ConfigParser import RawConfigParser
from StringIO import StringIO
from collections import OrderedDict

_log = logging.getLogger()

from clearwater_etcd_plugins.chronos.chronos_plugin import ChronosPlugin
from metaswitch.clearwater.cluster_manager.plugin_base import PluginParams
from metaswitch.clearwater.cluster_manager import alarm_constants


# Config Parser is not good at handling duplicate keys within sections
# This class can be passed into RawConfigParser to gather multiple entries
class MultiOrderedDict(OrderedDict):
    def __setitem__(self, key, value):
        if isinstance(value, list) and key in self:
            self[key].extend(value)
        else:
            super(MultiOrderedDict, self).__setitem__(key, value)


class TestChronosPlugin(unittest.TestCase):
    @mock.patch('clearwater_etcd_plugins.chronos.chronos_plugin.run_command')
    @mock.patch('clearwater_etcd_plugins.chronos.chronos_plugin.safely_write')
    @mock.patch('metaswitch.common.alarms.alarm_manager.get_alarm')
    def test_write_config(self, mock_get_alarm, mock_safely_write, mock_run_command):
        """Test chronos_plugin writes settings correctly with all possible server states"""

        # Create a plugin with dummy parameters
        plugin = ChronosPlugin(PluginParams(ip='10.0.0.1',
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
                                               alarm_constants.CHRONOS_NOT_YET_CLUSTERED)

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

        # Catch the call to reload chronos
        mock_run_command.assert_called_once_with('service chronos reload')

        # Check the plugin is attempting to write to the correct location
        self.assertEqual("/etc/chronos/chronos_cluster.conf", args[0][0])

        # ConfigParser can't parse plain strings in python 2.7
        # Load the config into a buffer and pass it in as a string like object
        buf = StringIO(args[0][1])
        config = RawConfigParser(dict_type=MultiOrderedDict)
        config.readfp(buf)

        # Check identity section
        self.assertEqual(config.get('identity', 'instance_id'), '18')
        self.assertEqual(config.get('identity', 'deployment_id'), '6')
        # Check cluster section
        self.assertEqual(config.get('cluster', 'localhost'), '10.0.0.1')
        self.assertTrue(all(ip in config.get('cluster', 'joining')
                            for ip in ("10.0.0.3", "10.0.0.4")))
        self.assertTrue(all(ip in config.get('cluster', 'node')
                            for ip in ("10.0.0.5", "10.0.0.6", "10.0.0.7")))
        self.assertTrue(all(ip in config.get('cluster', 'leaving')
                            for ip in ("10.0.0.10", "10.0.0.11")))
