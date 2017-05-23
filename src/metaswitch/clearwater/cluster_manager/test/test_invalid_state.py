#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


from mock import patch
from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import EtcdFactory
import json
from .test_base import BaseClusterTest
from time import sleep

class TestInvalidState(BaseClusterTest):

    def tearDown(self):
        self.close_synchronizers()

    @patch("etcd.Client", new=EtcdFactory)
    def test_invalid_state(self):
        """Force an invalid etcd state, and check that the clients don't try to
        change it"""
        client = EtcdFactory()
        invalid_state= {"10.0.0.1": "joining",
                        "10.0.0.2": "error",
                        "10.0.2.1": "leaving"}
        client.write("/test", json.dumps(invalid_state))
        self.make_and_start_synchronizers(3)
        client2 = self.syncs[0]._client
        sleep(0.5)

        end = json.loads(client2.read("/test").value)
        self.assertEqual(end, invalid_state)
