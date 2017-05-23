#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import unittest
from mock import patch
from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import SlowMockEtcdClient
from .contention_detecting_plugin import ContentionDetectingPlugin
import json
import os
from .test_base import BaseClusterTest


class TestContention(BaseClusterTest):

    @unittest.skipIf(os.environ.get("ETCD_IP"),
                     "Relies on in-memory etcd implementation")
    @unittest.skipUnless(os.environ.get("SLOW"), "SLOW=T not set")
    @patch("etcd.Client", new=SlowMockEtcdClient)
    def test_write_contention(self):
        # Create a cluster of 30 nodes, using a plugin that asserts if any work
        # is repeated (e.g. if on_cluster_changing() is called twice without the
        # cluster actually changing in between).
        self.make_and_start_synchronizers(30, klass=ContentionDetectingPlugin)
        mock_client = self.syncs[0]._client
        self.wait_for_all_normal(mock_client, required_number=30, tries=300)
        end = json.loads(mock_client.read("/test").value)

        # Check that the cluster ended up in a stable state (which won't have
        # happened if the plugin has hit an assertion)
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual("normal", end.get("10.0.0.19"))
        self.assertEqual("normal", end.get("10.0.0.29"))
        self.close_synchronizers()
