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

# This class is used as a side effect in mocking out os.path.exists, which is
# used in the plugin to check the system state via a set of state flags. This
# can be set up in each test to simulate a specific system state, rather than
# needing a separate side effect definition for each.
class mock_existing_files(object):
    def __init__(self, state_flags):
        self.existing_flags = state_flags

    def __call__(self, flag):
        return flag in self.existing_flags

class TestCassandraPlugin(unittest.TestCase):

    @mock.patch('metaswitch.common.alarms.alarm_manager.get_alarm')
    def get_plugin(self, mock_get_alarm):
        # Create a plugin with dummy parameters
        # Do this here to separate out the check for the alarm call
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
        return plugin

    def setUp(self):
        # Get a plugin for the test case
        self.plugin = self.get_plugin()

        # This test cluster view includes all possible node states
        self.test_cluster_view = {"10.0.0.1": "waiting to join",
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

        self.test_yaml_template = """\
listen_address: testing\n\
seed_provider:\n\
    - class_name: org.apache.cassandra.locator.SimpleSeedProvider\n\
      parameters:\n\
          - seeds: "127.0.0.1"\n\
"""

    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.path.exists')
    def test_cassandra_startup_no_refresh(self, mock_os_path):
        """Test the cassandra_plugin on_startup method without the force_refresh flag
           This should do nothing. As a first time startup the on_joining method would
           be responsible for creating the correct config."""

        # Return for all os.path.exists checks, to simulate no state flags
        flags = []
        mock_os_path.side_effect = mock_existing_files(flags)

        # Call startup actions, as the FSM would
        self.plugin.on_startup(self.test_cluster_view)

        # Check we only check the path exists once
        mock_os_path.assert_called_once_with("/etc/clearwater/force_cassandra_yaml_refresh")


    # run_command returns 0 if a command completes successfully, but python mocks
    # return 'True', i.e. 1. Force return value of 0 to simulate successes.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.run_command',\
                return_value=0)
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.safely_write')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.path.exists')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.remove')
    # The plugin uses check_output to get the latency value, so we return 100000.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.subprocess.check_output',\
                return_value=100000)
    def test_cassandra_startup_yaml_refresh(self,\
                                            mock_check_output,\
                                            mock_os_remove,\
                                            mock_os_path,\
                                            mock_safely_write,\
                                            mock_run_command):
        """Test cassandra_plugin on_startup, with the force_refresh flag set.
           This represents the state after an upgrade where we want the plugin to
           pick up any changes to the yaml template etc. This test checks we write
           the yaml and topology files correctly"""

        # Set up the state to be returned by mock_path_exists
        flags = ["/etc/clearwater/force_cassandra_yaml_refresh", "/etc/cassandra/cassandra.yaml"]
        mock_os_path.side_effect = mock_existing_files(flags)

        # Call startup actions, as the FSM would. As 'force_cassandra_yaml_refresh'
        # is in place, as is the case on upgrade, we test the full 'on_startup' flow
        with mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.open', mock.mock_open(read_data=self.test_yaml_template), create=True) as mock_open:
            self.plugin.on_startup(self.test_cluster_view)

        mock_open.assert_called_once_with("/usr/share/clearwater/cassandra/cassandra.yaml.template")

        # Set expected calls for the mock commands
        path_exists_call_list = \
            [mock.call("/etc/clearwater/force_cassandra_yaml_refresh"),
             mock.call(self.plugin.CASSANDRA_YAML_FILE),
             mock.call(self.plugin.BOOTSTRAP_IN_PROGRESS_FLAG),
             mock.call(self.plugin.BOOTSTRAP_IN_PROGRESS_FLAG),
             mock.call("/etc/clearwater/force_cassandra_yaml_refresh")]

        path_remove_call_list = \
            [mock.call("/etc/cassandra/cassandra.yaml"),
             mock.call("/etc/clearwater/force_cassandra_yaml_refresh")]

        # These calls cover restarting cassandra, and the commands called by 
        # the plugin in wait_for_cassandra.
        run_command_call_list = \
            [mock.call("start-stop-daemon -K -p /var/run/cassandra/cassandra.pid -R TERM/30/KILL/5"),
             mock.call("/usr/share/clearwater/bin/poll_cassandra.sh --no-grace-period", log_error=False),
             mock.call("sudo service clearwater-infrastructure restart")]

        mock_os_path.assert_has_calls(path_exists_call_list)
        mock_os_remove.assert_has_calls(path_remove_call_list)
        mock_run_command.assert_has_calls(run_command_call_list)

        # Here we are checking that the plugin writes to the topology and yaml
        # files correctly. The tests below will not repeat this effort.

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
        self.assertEqual(self.plugin.files()[0], yaml_write_args[0][0])

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
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.path.exists')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.remove')
    # The plugin uses check_output to get the latency value, so we return 100000.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.subprocess.check_output',\
                return_value=100000)
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.CassandraPlugin.wait_for_cassandra',\
                return_value=True)
    def test_cassandra_joining_cluster(self,\
                                       mock_wait_cassandra,\
                                       mock_check_output,\
                                       mock_os_remove,\
                                       mock_os_path,\
                                       mock_safely_write,\
                                       mock_run_command):
        """Test the cassandra_plugin joining process for a first time bootstrap
           This is a first time boot, and so we should remove the data directory
           and perform a full destructive restart."""
        # Set up conditions and test data
        flags = [self.plugin.CASSANDRA_YAML_FILE]
        mock_os_path.side_effect = mock_existing_files(flags)

        # Call join cluster as the FSM would
        with mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.open', mock.mock_open(read_data=self.test_yaml_template), create=True) as mock_open:
            self.plugin.on_joining_cluster(self.test_cluster_view)

        # Mock open will be called to read the yaml template, and to write the bootstrapping flag.
        # Due to the difficulty in testing, we don't actually set the flag for later in this test,
        # but it's functionality is tested below.
        mock_open_call_list = \
            [mock.call("/usr/share/clearwater/cassandra/cassandra.yaml.template"),
             mock.call(self.plugin.BOOTSTRAP_IN_PROGRESS_FLAG, 'a')]
        # We need the any_order=True argument, as there are a number of calls we catch in
        # reading the yaml that we do not want to catch. e.g.  `call().read(1024)`
        mock_open.assert_has_calls(mock_open_call_list, any_order=True)

        # Check the additional calls that we should make when destructive_restart = True actually happen.
        run_command_call_list = \
            [mock.call("start-stop-daemon -K -p /var/run/cassandra/cassandra.pid -R TERM/30/KILL/5"),
             mock.call("rm -rf /var/lib/cassandra/"),
             mock.call("mkdir -m 755 /var/lib/cassandra"),
             mock.call("chown -R cassandra /var/lib/cassandra")]
        mock_run_command.assert_has_calls(run_command_call_list)


    # run_command returns 0 if a command completes successfully, but python mocks
    # return 'True', i.e. 1. Force return value of 0 to simulate successes.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.run_command',\
                return_value=0)
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.safely_write')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.path.exists')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.remove')
    # The plugin uses check_output to get the latency value, so we return 100000.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.rename')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.subprocess.check_output',\
                return_value=100000)
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.CassandraPlugin.wait_for_cassandra',\
                return_value=True)
    def test_cassandra_bootstrap_in_progress(self,\
                                             mock_wait_cassandra,\
                                             mock_check_output,\
                                             mock_os_rename,\
                                             mock_os_remove,\
                                             mock_os_path,\
                                             mock_safely_write,\
                                             mock_run_command):
        """Test the cassandra_plugin when the bootstrap_in_progress flag is set.
           This tests that when we call on into write_new_cassandra_config from
           on_joining_cluster, we do not kill cassandra while it is still in the
           initial bootstrapping state. Doing so could render us unable to join
           the cluster properly again."""

        # Set up the state to be returned by mock_path_exists
        flags = [self.plugin.CASSANDRA_YAML_FILE,
                 self.plugin.BOOTSTRAP_IN_PROGRESS_FLAG]
        mock_os_path.side_effect = mock_existing_files(flags)

        # Call join cluster as the FSM would
        with mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.open', mock.mock_open(read_data=self.test_yaml_template), create=True) as mock_open:
            self.plugin.on_joining_cluster(self.test_cluster_view)

        mock_open.assert_called_once_with("/usr/share/clearwater/cassandra/cassandra.yaml.template")

        # We expect that the bootstrapping flag should prevent us calling run_command
        mock_os_rename.assert_called_once_with(self.plugin.BOOTSTRAP_IN_PROGRESS_FLAG,
                                               self.plugin.BOOTSTRAPPED_FLAG)

        # Set expected calls for the mock commands
        path_exists_call_list = \
             [mock.call(self.plugin.CASSANDRA_YAML_FILE),
             mock.call(self.plugin.BOOTSTRAP_IN_PROGRESS_FLAG),
             mock.call(self.plugin.BOOTSTRAPPED_FLAG),
             mock.call(self.plugin.BOOTSTRAP_IN_PROGRESS_FLAG),
             mock.call(self.plugin.BOOTSTRAP_IN_PROGRESS_FLAG),
             mock.call("/etc/clearwater/force_cassandra_yaml_refresh")]

        path_remove_call_list = \
            [mock.call("/etc/cassandra/cassandra.yaml")]

        mock_os_path.assert_has_calls(path_exists_call_list)
        mock_os_remove.assert_has_calls(path_remove_call_list)
        mock_run_command.assert_not_called()


    # run_command returns 0 if a command completes successfully, but python mocks
    # return 'True', i.e. 1. Force return value of 0 to simulate successes.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.run_command',\
                return_value=0)
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.safely_write')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.path.exists')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.remove')
    # The plugin uses check_output to get the latency value, so we return 100000.
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.os.rename')
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.subprocess.check_output',\
                return_value=100000)
    @mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.CassandraPlugin.wait_for_cassandra',\
                return_value=True)
    def test_cassandra_bootstrapped(self,\
                                    mock_wait_cassandra,\
                                    mock_check_output,\
                                    mock_os_rename,\
                                    mock_os_remove,\
                                    mock_os_path,\
                                    mock_safely_write,\
                                    mock_run_command):
        """Test the cassandra_plugin when the bootstrapped flag is set.
           This tests that when we call on into write_new_cassandra_config from
           on_joining_cluster, we kill cassandra but do not remove our data directory,
           as this should only happen on the first time joining a cluster, to prevent
           data loss."""

        # Set up the state to be returned by mock_path_exists
        flags = [self.plugin.CASSANDRA_YAML_FILE,
                 self.plugin.BOOTSTRAPPED_FLAG]
        mock_os_path.side_effect = mock_existing_files(flags)

        # Call join cluster as the FSM would
        with mock.patch('clearwater_etcd_plugins.clearwater_cassandra.cassandra_plugin.open', mock.mock_open(read_data=self.test_yaml_template), create=True) as mock_open:
            self.plugin.on_joining_cluster(self.test_cluster_view)

        mock_open.assert_called_once_with("/usr/share/clearwater/cassandra/cassandra.yaml.template")

        # Set expected calls for the mock commands
        path_exists_call_list = \
             [mock.call(self.plugin.CASSANDRA_YAML_FILE),
             mock.call(self.plugin.BOOTSTRAP_IN_PROGRESS_FLAG),
             mock.call(self.plugin.BOOTSTRAPPED_FLAG),
             mock.call(self.plugin.BOOTSTRAP_IN_PROGRESS_FLAG),
             mock.call("/etc/clearwater/force_cassandra_yaml_refresh")]

        path_remove_call_list = \
            [mock.call("/etc/cassandra/cassandra.yaml")]

        mock_os_path.assert_has_calls(path_exists_call_list)
        mock_os_remove.assert_has_calls(path_remove_call_list)
        # Check that the only call to run_command was to stop
        # cassandra, not to remove the data directory
        mock_run_command.assert_called_once_with(\
            "start-stop-daemon -K -p /var/run/cassandra/cassandra.pid -R TERM/30/KILL/5")


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
        """Test the cassandra_plugin leaving process
        We should make sure that the bootstrapped flag is removed once we leave"""
        # Set up the state to be returned by mock_path_exists. We wouldn't
        # normally expect both the bootstrap_in_progress and bootstrapping
        # flags to be present at the same time, but to make sure we remove
        # them without needing two near identical tests, we'll set them both here.
        flags = [self.plugin.CASSANDRA_YAML_FILE,
                 self.plugin.BOOTSTRAP_IN_PROGRESS_FLAG,
                 self.plugin.BOOTSTRAPPED_FLAG]
        mock_os_path.side_effect = mock_existing_files(flags)

        # Call leave cluster as the FSM would
        self.plugin.on_leaving_cluster(self.test_cluster_view)

        mock_get_alarm.assert_called_with('cluster-manager',
                                          alarm_constants.CASSANDRA_NOT_YET_DECOMMISSIONED)

        # Set the expected calls to the mock commands, making sure that we run
        # the nodetool decommission command
        run_command_call_list = \
            [mock.call("/usr/share/clearwater/bin/poll_cassandra.sh --no-grace-period", log_error=False),
             mock.call("nodetool decommission", self.plugin._sig_namespace)]

        mock_run_command.assert_has_calls(run_command_call_list)

        path_exists_call_list = \
            [mock.call(self.plugin.CASSANDRA_YAML_FILE),
             mock.call(self.plugin.BOOTSTRAP_IN_PROGRESS_FLAG),
             mock.call(self.plugin.BOOTSTRAPPED_FLAG)]
        path_remove_call_list = \
            [mock.call(self.plugin.CASSANDRA_YAML_FILE),
             mock.call(self.plugin.BOOTSTRAP_IN_PROGRESS_FLAG),
             mock.call(self.plugin.BOOTSTRAPPED_FLAG)]

        mock_os_path.assert_has_calls(path_exists_call_list)
        mock_os_remove.assert_has_calls(path_remove_call_list)
