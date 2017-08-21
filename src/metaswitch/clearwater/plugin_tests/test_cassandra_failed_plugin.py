# @file test_cassandra_failed_plugin.py
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

from clearwater_etcd_plugins.clearwater_cassandra.cassandra_failed_plugin import CassandraFailedPlugin

class TestCassandraFailedPlugin(unittest.TestCase):
    @mock.patch.object(CassandraFailedPlugin, 'remove_node')
    def test_cassandra_failed_leaving_cluster(self,\
                                              mock_remove_node):
        """Test the cassandra_failed_plugin leaving cluster process"""

        # Create a plugin with dummy parameters
        plugin = CassandraFailedPlugin(key="etcd_key/etcd_cluster_key/clustering/cassandra",
                                       ip='10.0.0.1')

        # Build a cluster_view that includes all possible node states
        cluster_view = {"10.0.0.1": "normal"}

        plugin.on_leaving_cluster(cluster_view)

        mock_remove_node.assert_called_once_with()
