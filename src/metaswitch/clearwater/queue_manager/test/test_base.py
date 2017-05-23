#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import unittest
from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import EtcdFactory
from time import sleep
from threading import Thread
from mock import patch
import json

class BaseQueueTest(unittest.TestCase):
    @patch("etcd.Client", new=EtcdFactory)
    def set_initial_val(self, queue_config):
        # Write some initial data into the key and start the synchronizer
        self._e._client.write("/clearwater/local/configuration/queue_test", queue_config)
        thread = Thread(target=self._e.main_wrapper)
        thread.daemon=True
        thread.start()

    @patch("etcd.Client", new=EtcdFactory)
    def tearDown(self):
        # Allow the EtcdSynchronizer to exit
        self._e._terminate_flag = True
        sleep(1)

    def wait_for_success_or_fail(self, pass_criteria):
        for x in range(10):
            val = json.loads(self._e._client.return_global_data())
            if pass_criteria(val):
                return True
            sleep(1)
        print "Queue config not updated as expected, final value was: ", val
        return False
