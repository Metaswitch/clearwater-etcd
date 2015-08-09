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
