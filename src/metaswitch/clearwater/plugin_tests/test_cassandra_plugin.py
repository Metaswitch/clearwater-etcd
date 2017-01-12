# @file test_cassandra_plugin.py
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
import yaml

_log = logging.getLogger()

from clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin import CassandraPlugin
from metaswitch.clearwater.cluster_manager.plugin_base import PluginParams
from metaswitch.clearwater.cluster_manager import alarm_constants
from metaswitch.clearwater.cluster_manager.plugin_utils import WARNING_HEADER

class TestCassandraPlugin(unittest.TestCase):
    # run_command returns 0 if a command completes successfully, but python mocks
    # return 'True', i.e. 1. Force return value of 0 to simulate successes.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.run_command',\
                return_value=0)
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.safely_write')
    @mock.patch('metaswitch.common.alarms.alarm_manager.get_alarm')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.path.exists')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.remove')
    # The plugin uses check_output to get the latency value, so we return 100000.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.subprocess.check_output',\
                return_value=100000)
    def test_cassandra_startup(self,\
                               mock_check_output,\
                               mock_os_remove,\
                               mock_os_path,\
                               mock_get_alarm,\
                               mock_safely_write,\
                               mock_run_command):
        """Test the cassandra_plugin startup process"""

        # Create a plugin with dummy parameters
        plugin = CassandraPlugin(PluginParams(ip='10.0.0.1',
                                              mgmt_ip='10.0.1.1',
                                              local_site='local_site',
                                              remote_site='remote_site',
                                              remote_cassandra_seeds='10.2.2.1',
                                              signaling_namespace='',
                                              uuid=uuid.UUID('92a674aa-a64b-4549-b150-596fd466923f'),
                                              etcd_key='etcd_key',
                                              etcd_cluster_key='etcd_cluster_key'))

        # We expect this alarm to be called on creation of the plugin
        mock_get_alarm.assert_called_once_with('cluster-manager',
                                               alarm_constants.CASSANDRA_NOT_YET_CLUSTERED)

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

        # Set up conditions and test data
        mock_os_path.return_value = True

        yaml_template = """\
listen_address: testing\n\
seed_provider:\n\
    - class_name: org.apache.cassandra.locator.SimpleSeedProvider\n\
      parameters:\n\
          - seeds: "127.0.0.1"\n\
"""

        # Call startup actions, as the FSM would, assuming 'force_cassandra_yaml_refresh'
        # is in place, as is the case on upgrade, to test the full 'on_startup' flow
        with mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.open', mock.mock_open(read_data=yaml_template), create=True) as mock_open:
            plugin.on_startup(cluster_view)

        mock_open.assert_called_once_with("/usr/share/clearwater/cassandra/cassandra.yaml.template")

        # Set expected calls for the mock commands
        path_exists_call_list = \
            [mock.call("/etc/clearwater/force_cassandra_yaml_refresh"),
             mock.call("/etc/cassandra/cassandra.yaml"),
             mock.call("/etc/clearwater/force_cassandra_yaml_refresh")]

        path_remove_call_list = \
            [mock.call("/etc/cassandra/cassandra.yaml"),
             mock.call("/etc/clearwater/force_cassandra_yaml_refresh")]

        run_command_call_list = \
            [mock.call("start-stop-daemon -K -p /var/run/cassandra/cassandra.pid -R TERM/30/KILL/5")]

        mock_os_path.assert_has_calls(path_exists_call_list)
        mock_os_remove.assert_has_calls(path_remove_call_list)
        mock_run_command.assert_has_calls(run_command_call_list)

        # Pull out the call for writing the topology file
        topology_write_args = mock_safely_write.call_args_list[0]
        # Check the write location matches the plugin files location
        self.assertEqual("/etc/cassandra/cassandra-rackdc.properties", topology_write_args[0][0])
        # Check write was formatted correctly
        exp_topology = WARNING_HEADER + "\ndc=local_site\nrack=RAC1\n"
        self.assertEqual(exp_topology, topology_write_args[0][1])

        # Pull out the call for writing the yaml file
        yaml_write_args = mock_safely_write.call_args_list[1]
        # Check the write location matches the plugin files location
        self.assertEqual(plugin.files()[0], yaml_write_args[0][0])

        # Parse config, and test we are writing correct values
        yaml_string = yaml_write_args[0][1]
        test_doc = yaml.load(yaml_string)

        self.assertEqual(test_doc["listen_address"], '10.0.0.1')
        self.assertEqual(test_doc["broadcast_rpc_address"], '10.0.0.1')
        self.assertEqual(test_doc["endpoint_snitch"], "GossipingPropertyFileSnitch")

        expected_seeds = ['10.0.0.5', '10.0.0.6', '10.0.0.7']
        seed_string = test_doc["seed_provider"][0]["parameters"][0]["seeds"]
        for seed in expected_seeds:
            self.assertTrue(seed in seed_string)

    # run_command returns 0 if a command completes successfully, but python mocks
    # return 'True', i.e. 1. Force return value of 0 to simulate successes.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.run_command',\
                return_value=0)
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.safely_write')
    @mock.patch('metaswitch.common.alarms.alarm_manager.get_alarm')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.path.exists')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.remove')
    # The plugin uses check_output to get the latency value, so we return 100000.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.subprocess.check_output',\
                return_value=100000)
    def test_cassandra_joining_cluster(self,\
                                       mock_check_output,\
                                       mock_os_remove,\
                                       mock_os_path,\
                                       mock_get_alarm,\
                                       mock_safely_write,\
                                       mock_run_command):
        """Test the cassandra_plugin joining process"""

        # Create a plugin with dummy parameters
        plugin = CassandraPlugin(PluginParams(ip='10.0.0.1',
                                              mgmt_ip='10.0.1.1',
                                              local_site='local_site',
                                              remote_site='remote_site',
                                              remote_cassandra_seeds='10.2.2.1',
                                              signaling_namespace='',
                                              uuid=uuid.UUID('92a674aa-a64b-4549-b150-596fd466923f'),
                                              etcd_key='etcd_key',
                                              etcd_cluster_key='etcd_cluster_key'))

        # We expect this alarm to be called on creation of the plugin
        mock_get_alarm.assert_called_once_with('cluster-manager',
                                               alarm_constants.CASSANDRA_NOT_YET_CLUSTERED)

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

        # Set up conditions and test data
        mock_os_path.return_value = True

        yaml_template = """\
listen_address: testing\n\
seed_provider:\n\
    - class_name: org.apache.cassandra.locator.SimpleSeedProvider\n\
      parameters:\n\
          - seeds: "127.0.0.1"\n\
"""

        # Call join cluster as the FSM would
        with mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.open', mock.mock_open(read_data=yaml_template), create=True) as mock_open:
            plugin.on_joining_cluster(cluster_view)

        mock_open.assert_called_once_with("/usr/share/clearwater/cassandra/cassandra.yaml.template")

        # Check the additional calls that we should make when destructive_restart = True actually happen,
        # and that we run the cassandra schema at the end
        run_command_call_list = \
            [mock.call("start-stop-daemon -K -p /var/run/cassandra/cassandra.pid -R TERM/30/KILL/5"),
             mock.call("rm -rf /var/lib/cassandra/"),
             mock.call("mkdir -m 755 /var/lib/cassandra"),
             mock.call("chown -R cassandra /var/lib/cassandra"),
             mock.call("/usr/share/clearwater/bin/poll_cassandra.sh --no-grace-period", log_error=False),
             mock.call("sudo service clearwater-infrastructure restart")]

        mock_run_command.assert_has_calls(run_command_call_list)

    # run_command returns 0 if a command completes successfully, but python mocks
    # return 'True', i.e. 1. Force return value of 0 to simulate successes.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.run_command',\
                return_value=0)
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.safely_write')
    @mock.patch('metaswitch.common.alarms.alarm_manager.get_alarm')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.path.exists')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.remove')
    # The plugin uses check_output to get the latency value, so we return 100000.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.subprocess.check_output',\
                return_value=100000)
    def test_cassandra_leaving_cluster(self,\
                                       mock_check_output,\
                                       mock_os_remove,\
                                       mock_os_path,\
                                       mock_get_alarm,\
                                       mock_safely_write,\
                                       mock_run_command):
        """Test the cassandra_plugin leaving process"""

        # Create a plugin with dummy parameters
        plugin = CassandraPlugin(PluginParams(ip='10.0.0.1',
                                              mgmt_ip='10.0.1.1',
                                              local_site='local_site',
                                              remote_site='remote_site',
                                              remote_cassandra_seeds='10.2.2.1',
                                              signaling_namespace='',
                                              uuid=uuid.UUID('92a674aa-a64b-4549-b150-596fd466923f'),
                                              etcd_key='etcd_key',
                                              etcd_cluster_key='etcd_cluster_key'))

        # We expect this alarm to be called on creation of the plugin
        mock_get_alarm.assert_called_once_with('cluster-manager',
                                               alarm_constants.CASSANDRA_NOT_YET_CLUSTERED)

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

        # Set up conditions and test data
        mock_os_path.return_value = True

        # Call leave cluster as the FSM would
        plugin.on_leaving_cluster(cluster_view)

        mock_get_alarm.assert_called_with('cluster-manager',
                                          alarm_constants.CASSANDRA_NOT_YET_DECOMMISSIONED)

        # Set the expected calls to the mock commands, making sure that we run
        # the nodetool decommission command
        run_command_call_list = \
            [mock.call("/usr/share/clearwater/bin/poll_cassandra.sh --no-grace-period", log_error=False),
             mock.call("nodetool decommission", plugin._sig_namespace)]

        mock_run_command.assert_has_calls(run_command_call_list)

        path_exists_call_list = \
            [mock.call("/etc/cassandra/cassandra.yaml")]
        path_remove_call_list = \
            [mock.call("/etc/cassandra/cassandra.yaml")]

        mock_os_path.assert_has_calls(path_exists_call_list)
        mock_os_remove.assert_has_calls(path_remove_call_list)
