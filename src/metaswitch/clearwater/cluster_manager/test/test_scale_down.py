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
from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import EtcdFactory
from metaswitch.clearwater.cluster_manager.etcd_synchronizer \
    import EtcdSynchronizer
from .dummy_plugin import DummyPlugin
import json
from .test_base import BaseClusterTest


class TestScaleDown(BaseClusterTest):

    @patch("etcd.Client", new=EtcdFactory)
    def test_scale_down(self):
        # Start with a stable cluster of four nodes
        syncs = [EtcdSynchronizer(DummyPlugin(None), ip) for ip in
                 ['10.0.1.1',
                  '10.0.1.2',
                  '10.0.1.3',
                  '10.0.1.4',
                  ]]
        mock_client = syncs[0]._client
        mock_client.write("/test", json.dumps({"10.0.1.1": "normal",
                                               "10.0.1.2": "normal",
                                               "10.0.1.3": "normal",
                                               "10.0.1.4": "normal",
                                               }))
        for s in syncs:
            s.start_thread()

        # Make the second and fourth nodes leave
        syncs[1].leave_cluster()
        syncs[3].leave_cluster()

        self.wait_for_all_normal(mock_client, required_number=2, tries=50)

        # Check that it's left and the cluster is stable
        end = json.loads(mock_client.read("/test").value)
        self.assertEqual("normal", end.get("10.0.1.1"))
        self.assertEqual("normal", end.get("10.0.1.3"))

        self.assertEqual(None, end.get("10.0.1.2"))
        self.assertEqual(None, end.get("10.0.1.4"))
        for s in syncs:
            s.terminate()
