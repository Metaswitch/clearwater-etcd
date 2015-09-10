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

from .etcdtestbase import GenericEtcdTests

class ClusterMgrFVTest(GenericEtcdTests):
    def cluster_mgr_test(self, before_fn, during_fn):
        ips = ['127.0.0.100', '127.0.0.101', '127.0.0.102']
        self.initialise_servers(*ips)
        client = self.servers['127.0.0.100'].client()
        client.write("/dummy/", "{}")

        if before_fn:
            before_fn()

        mgr1 = self.add_cluster_manager('127.0.0.100')

        mgr2 = self.add_cluster_manager('127.0.0.101', during_fn)
        mgr3 = self.add_cluster_manager('127.0.0.102')

        expected = {'127.0.0.100': 'normal',
                    '127.0.0.101': 'normal',
                    '127.0.0.102': 'normal'}

        mgr1.wait_for(expected)
        mgr2.wait_for(expected)

        self.assertEqual(mgr1.value(), expected)
        self.assertEqual(mgr2.value(), expected)

        # Don't assert anything about mgr3 - we may have killed that server


    def test_mainline(self):
        self.cluster_mgr_test(before_fn=None, during_fn=None)

    def test_single_server_restart(self):
        self.cluster_mgr_test(before_fn=None, during_fn=self.restart_local_server)

    def test_quorum_restart(self):
        self.cluster_mgr_test(before_fn=None, during_fn=self.restart_quorum)

    def test_adding_etcd_nodes(self):
        self.cluster_mgr_test(before_fn=None, during_fn=self.add_five_nodes)

    def test_1k_writes(self):
        self.cluster_mgr_test(before_fn=None, during_fn=self.do_1k_writes)


