#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2015
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


import unittest
from mock import patch
from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import ExceptionMockEtcdClient
import json
from .test_base import BaseClusterTest
import os


class TestResilience(BaseClusterTest):

    @unittest.skipIf(os.environ.get("ETCD_IP"),
                     "Relies on in-memory etcd implementation")
    @patch("etcd.Client", new=ExceptionMockEtcdClient)
    def test_resilience_to_exceptions(self):
        self.make_and_start_synchronizers(15)
        mock_client = self.syncs[0]._client

        # Check that the cluster stabilizes, even though etcd is throwing
        # exceptions 50% of the time
        self.wait_for_all_normal(mock_client, required_number=15, tries=300)
        end = json.loads(mock_client.read_noexcept("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual("normal", end.get("10.0.0.14"))
        self.close_synchronizers()
