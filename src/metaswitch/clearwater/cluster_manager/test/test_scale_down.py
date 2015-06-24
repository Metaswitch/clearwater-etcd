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
from .dummy_plugin import DummyPlugin
import json
from .test_base import BaseClusterTest


class TestScaleDown(BaseClusterTest):

    @patch("etcd.Client", new=EtcdFactory)
    def test_scale_down(self):
        # Start with a stable cluster of two nodes
        sync1 = EtcdSynchronizer(DummyPlugin(None), '10.0.1.1')
        sync2 = EtcdSynchronizer(DummyPlugin(None), '10.0.1.2')
        mock_client = sync1._client
        mock_client.write("/test", json.dumps({"10.0.1.1": "normal",
                                               "10.0.1.2": "normal"}))
        for s in [sync1, sync2]:
            s.start_thread()

        # Make the second node leave
        sync2.leave_cluster()
        sync2.thread.join(20)
        sync2.terminate()
        self.wait_for_all_normal(mock_client, required_number=1)

        # Check that it's left and the cluster is stable
        end = json.loads(mock_client.read("/test").value)
        self.assertEqual(None, end.get("10.0.1.2"))
        self.assertEqual("normal", end.get("10.0.1.1"))
        sync1.terminate()
