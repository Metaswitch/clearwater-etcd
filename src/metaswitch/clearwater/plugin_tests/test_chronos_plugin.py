# @file test_chronos_plugin.py
#
# project clearwater - ims in the cloud
# copyright (c) 2016  metaswitch networks ltd
#
# this program is free software: you can redistribute it and/or modify it
# under the terms of the gnu general public license as published by the
# free software foundation, either version 3 of the license, or (at your
# option) any later version, along with the "special exception" for use of
# the program along with ssl, set forth below. this program is distributed
# in the hope that it will be useful, but without any warranty;
# without even the implied warranty of merchantability or fitness for
# a particular purpose.  see the gnu general public license for more
# details. you should have received a copy of the gnu general public
# license along with this program.  if not, see
# <http://www.gnu.org/licenses/>.
#
# the author can be reached by email at clearwater@metaswitch.com or by
# post at metaswitch networks ltd, 100 church st, enfield en2 6bq, uk
#
# special exception
# metaswitch networks ltd  grants you permission to copy, modify,
# propagate, and distribute a work formed by combining openssl with the
# software, or a work derivative of such a combination, even if such
# copying, modification, propagation, or distribution would otherwise
# violate the terms of the gpl. you must comply with the gpl in all
# respects for all of the code used other than openssl.
# "openssl" means openssl toolkit software distributed by the openssl
# project and licensed under the openssl licenses, or a work based on such
# software and licensed under the openssl licenses.
# "openssl licenses" means the openssl license and original ssleay license
# under which the openssl project distributes the openssl toolkit software,
# as those licenses appear in the file license-openssl.

import unittest
import mock
import logging
import uuid

_log = logging.getLogger()

from textwrap import dedent
from metaswitch.clearwater.cluster_manager.plugin_utils import WARNING_HEADER
from clearwater_etcd_plugins.chronos.chronos_plugin import ChronosPlugin
from metaswitch.clearwater.cluster_manager.plugin_base import PluginParams
from metaswitch.clearwater.cluster_manager import alarm_constants, constants


def calculate_contents(cluster_view, current_server, uuid):
    joining = [constants.JOINING_ACKNOWLEDGED_CHANGE,
               constants.JOINING_CONFIG_CHANGED]
    staying = [constants.NORMAL_ACKNOWLEDGED_CHANGE,
               constants.NORMAL_CONFIG_CHANGED,
               constants.NORMAL]
    leaving = [constants.LEAVING_ACKNOWLEDGED_CHANGE,
               constants.LEAVING_CONFIG_CHANGED]

    joining_servers = ([k for k, v in cluster_view.iteritems()
                        if v in joining])
    staying_servers = ([k for k, v in cluster_view.iteritems()
                        if v in staying])
    leaving_servers = ([k for k, v in cluster_view.iteritems()
                        if v in leaving])

    uuid_bytes = uuid.bytes
    instance_id = ord(uuid_bytes[0]) & 0b0111111
    deployment_id = ord(uuid_bytes[1]) & 0b00000111 

    contents = dedent('''\
        {}
        [identity]
        instance_id = {}
        deployment_id = {}

        [cluster]
        localhost = {}
        ''').format(WARNING_HEADER, instance_id, deployment_id, current_server)

    for node in joining_servers:
        contents += 'joining = {}\n'.format(node)
    for node in staying_servers:
        contents += 'node = {}\n'.format(node)
    for node in leaving_servers:
        contents += 'leaving = {}\n'.format(node)

    return contents


class TestChronosPlugin(unittest.TestCase):
    @mock.patch('clearwater_etcd_plugins.chronos.chronos_plugin.run_command')
    @mock.patch('clearwater_etcd_plugins.chronos.chronos_plugin.safely_write')
    @mock.patch('metaswitch.common.alarms.alarm_manager.get_alarm')
    def test_write_config(self, mock_get_alarm, mock_safely_write, mock_run_command):
        """Create a plugin with dummy parameters"""
        test_uuid = uuid.uuid4()
        plugin = ChronosPlugin(PluginParams(ip='10.0.0.1',
                                            mgmt_ip='10.0.1.1',
                                            local_site='local_site',
                                            remote_site='remote_site',
                                            remote_cassandra_seeds='',
                                            signaling_namespace='',
                                            uuid=test_uuid,
                                            etcd_key='etcd_key',
                                            etcd_cluster_key='etcd_cluster_key'))

        # We expect this alarm to be called on creation of the plugin
        mock_get_alarm.assert_called_once_with('cluster-manager', alarm_constants.CHRONOS_NOT_YET_CLUSTERED)

        """Have the plugin write chronos cluster settings"""
        # First calculate the contents of the file that should be written
        filename = '/etc/chronos/chronos_cluster.conf'
        cluster_view =  {"10.0.0.1": "normal", "10.0.0.2": "joining, config changed", "10.0.0.3": "joining, acknowledged change", "10.0.0.4": "leaving, config changed", "10.0.0.5": "leaving, acknowledged change"}
        current_server='10.0.0.1'
        contents = calculate_contents(cluster_view, current_server, test_uuid)

        # Call the plugin to write the settings itself, and catch and compare the file contents
        plugin.write_cluster_settings(cluster_view)
        mock_safely_write.assert_called_once_with(filename, contents)
        # Catch the call to reload chronos
        mock_run_command.assert_called_once_with('service chronos reload')
