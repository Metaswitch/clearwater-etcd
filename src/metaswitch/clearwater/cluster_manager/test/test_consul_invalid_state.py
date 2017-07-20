#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2015
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


from mock import patch
from metaswitch.clearwater.etcd_shared.test.mock_python_consul import ConsulFactory
import json
from .test_consul import BaseConsulBackedClusterTest
from time import sleep

class TestInvalidState(BaseConsulBackedClusterTest):

    def tearDown(self):
        self.close_synchronizers()

    @patch("consul.Consul", new=ConsulFactory)
    def test_invalid_state(self):
        """Force an invalid state, and check that the clients don't try to
        change it"""
        client = ConsulFactory()
        invalid_state= {"10.0.0.1": "joining",
                        "10.0.0.2": "error",
                        "10.0.2.1": "leaving"}
        client.kv.put("test", json.dumps(invalid_state))
        self.make_and_start_synchronizers(3)
        client2 = self.syncs[0]._client
        sleep(0.5)

        (_, resp) = client2.get("test")
        end = json.loads(resp.get("Value"))
        self.assertEqual(end, invalid_state)
