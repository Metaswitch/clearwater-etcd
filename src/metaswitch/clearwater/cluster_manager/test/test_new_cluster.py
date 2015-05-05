#!/usr/bin/env python

import unittest
from mock import patch
from .mock_python_etcd import EtcdFactory, SlowMockEtcdClient
import json
import os
from .test_base import BaseClusterTest


class TestNewCluster(BaseClusterTest):

    @patch("etcd.Client", new=EtcdFactory)
    def test_new_cluster(self):
        """Create a new 3-node cluster and check that they all end up
        in NORMAL state"""
        self.make_and_start_synchronizers(3)
        mock_client = self.syncs[0]._client
        self.wait_for_all_normal(mock_client, required_number=3)

        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.0"))
        self.assertEqual("normal", end.get("10.0.0.1"))
        self.assertEqual("normal", end.get("10.0.0.2"))
        self.close_synchronizers()

    @patch("etcd.Client", new=EtcdFactory)
    def test_large_new_cluster(self):
        """Create a new 30-node cluster and check that they all end up
        in NORMAL state"""
        self.make_and_start_synchronizers(30)
        mock_client = self.syncs[0]._client
        self.wait_for_all_normal(mock_client, required_number=30, tries=300)

        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual("normal", end.get("10.0.0.19"))
        self.assertEqual("normal", end.get("10.0.0.29"))
        self.close_synchronizers()

    @unittest.skipIf(os.environ.get("ETCD_IP"),
                     "Relies on in-memory etcd implementation")
    @unittest.skipUnless(os.environ.get("SLOW"), "SLOW=T not set")
    @patch("etcd.Client", new=SlowMockEtcdClient)
    def test_large_new_cluster_with_delays(self):
        """Create a new 30-node cluster and check that they all end up
        in NORMAL state, even if etcd writes have a random delay that causes
        contention and retries"""
        self.make_and_start_synchronizers(30)
        mock_client = self.syncs[0]._client
        self.wait_for_all_normal(mock_client, required_number=30, tries=300)

        end = json.loads(mock_client.get("/test").value)
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual("normal", end.get("10.0.0.19"))
        self.assertEqual("normal", end.get("10.0.0.29"))
        self.close_synchronizers()
