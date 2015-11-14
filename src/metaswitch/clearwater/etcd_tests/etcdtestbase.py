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

logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))
logging.getLogger().setLevel(logging.INFO)

class EtcdTestBase(unittest.TestCase):
    def setUp(self):
        self.servers = {}
        self.pool = ["127.0.0.{}".format(last_byte)  for last_byte in range (100, 150)]

    def add_server(self, **kwargs):
        ip = self.pool.pop()
        server = EtcdServer(ip, **kwargs)
        self.servers[ip] = server
        return server

    def initialise_servers(self, n):
        ret = []
        srv1 = self.add_server()
        ret.append(srv1)
        srv1.waitUntilAlive()
        for _ in range(n-1):
            ret.append(self.add_server(existing=srv1._ip))
        [x.waitUntilAlive() for x in ret]
        return ret

    def tearDown(self):
        for server in self.servers.values():
            server.exit()
        EtcdServer.delete_datadir()

    def test_basic_clustering(self):
        s1, s2 = self.initialise_servers(2)

        hasOneLeader = s1.isLeader() != s2.isLeader()

        self.assertTrue(s1.memberList() == s2.memberList())
        self.assertEquals(2, len(s1.memberList()))
