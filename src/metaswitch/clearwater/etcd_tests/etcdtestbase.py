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

from time import sleep
import logging
import sys
import etcd
from threading import Thread
import unittest
import json
from .etcdserver import EtcdServer
from .etcdcluster import EtcdCluster

logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))
logging.getLogger().setLevel(logging.INFO)

class EtcdTestBase(unittest.TestCase):
    def test_basic_clustering(self):
        c = EtcdCluster(2)
        s1, s2 = c.servers.values()

        hasOneLeader = s1.isLeader() != s2.isLeader()

        self.assertTrue(s1.memberList() == s2.memberList())
        self.assertEquals(2, len(s1.memberList()))
        c.delete_datadir()

    def test_iss203(self):
        c = EtcdCluster(2)
        s1, s2 = c.servers.values()
        s3 = c.add_server(actually_start=False)
        s4 = c.add_server()
        s5 = c.add_server()
        s6 = c.add_server()

        # Try to start any failed nodes again (in the same way that Monit would
        # when live)
        sleep(2)

        s4.recover()
        s5.recover()
        s6.recover()

        sleep(2)

        s4.recover()
        s5.recover()
        s6.recover()

        sleep(2)

        s4.recover()
        s5.recover()
        s6.recover()

        sleep(2)

        nameless = [m for m in s1.memberList() if not m['name']]

        # s3 should have no name, but s4, s5 and s6 all should
        self.assertEquals(1, len(nameless))
        self.assertEquals(s1.memberList(), s4.memberList())
        self.assertEquals(s1.memberList(), s5.memberList())
        self.assertEquals(s1.memberList(), s6.memberList())
        c.delete_datadir()
