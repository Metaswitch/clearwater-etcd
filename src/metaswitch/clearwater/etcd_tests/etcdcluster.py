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

from shutil import rmtree
from .etcdserver import EtcdServer
from metaswitch.common.logging_config import configure_test_logging
configure_test_logging()


class EtcdCluster(object):
    def __init__(self, n=1):
        self.datadir = "./etcd_test_data"
        self.servers = {}
        self.pool = ["127.0.0.{}".format(last_byte)  for last_byte in range (100, 150)]
        self.initialise_servers(n)

    def get_live_server(self):
        for ip, server in self.servers.iteritems():
            if server.isAlive():
                return server

    def add_server(self, **kwargs):
        ip = self.pool.pop()
        existing_ip = None
        live_server = self.get_live_server()
        if live_server is not None:
            existing_ip = live_server._ip
        server = EtcdServer(ip, datadir=self.datadir, existing=existing_ip, **kwargs)
        self.servers[ip] = server
        return server

    def initialise_servers(self, n):
        ret = []
        srv1 = self.add_server()
        ret.append(srv1)
        srv1.waitUntilAlive()
        for _ in range(n-1):
            server = self.add_server()
            rc = server.waitUntilAlive()
            while not rc:
                server.recover()
                rc = server.waitUntilAlive()
            ret.append(server)

        return ret

    def __del__(self):
        self.delete_datadir()

    def delete_datadir(self):
        rmtree(self.datadir, True)

