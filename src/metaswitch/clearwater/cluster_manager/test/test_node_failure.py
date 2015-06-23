#!/usr/bin/env python

# Project Clearwater - IMS in the Cloud
# Copyright (C) 2015 Metaswitch Networks Ltd
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


from mock import patch
from .mock_python_etcd import EtcdFactory
from metaswitch.clearwater.cluster_manager.etcd_synchronizer \
    import EtcdSynchronizer
from metaswitch.clearwater.cluster_manager.null_plugin import NullPlugin
from .dummy_plugin import DummyPlugin
from .fail_partway_through_plugin import FailPlugin
from time import sleep
import json
from .test_base import BaseClusterTest


class TestNodeFailure(BaseClusterTest):

    @patch("etcd.Client", new=EtcdFactory)
    def test_failure(self):

        # Create synchronisers, using a FailPlugin for one which will crash and
        # not complete (simulating a failed node)
        sync1 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.1')
        sync2 = EtcdSynchronizer(FailPlugin(None), '10.0.0.2')
        sync3 = EtcdSynchronizer(DummyPlugin(None), '10.0.0.3')
        mock_client = sync1._client
        for s in [sync1, sync2, sync3]:
            s.start_thread()

        # After a few seconds, the scale-up will still not have completed
        sleep(3)
        end = json.loads(mock_client.read("/test").value)
        self.assertNotEqual("normal", end.get("10.0.0.1"))
        self.assertNotEqual("normal", end.get("10.0.0.2"))
        self.assertNotEqual("normal", end.get("10.0.0.3"))

        # Start a synchroniser to take 10.0.0.2's place
        sync2.terminate()
        error_syncer = EtcdSynchronizer(NullPlugin('/test'),
                                        '10.0.0.2',
                                        force_leave=True)
        error_syncer.mark_node_failed()
        error_syncer.leave_cluster()
        error_syncer.start_thread()

        # 10.0.0.2 will be removed from the cluster, and the cluster will
        # stabilise
        sleep(3)
        end = json.loads(mock_client.read("/test").value)
        self.assertEqual("normal", end.get("10.0.0.1"))
        self.assertEqual("normal", end.get("10.0.0.3"))
        self.assertEqual(None, end.get("10.0.0.2"))
        for s in [sync1, sync3, error_syncer]:
            s.terminate()
