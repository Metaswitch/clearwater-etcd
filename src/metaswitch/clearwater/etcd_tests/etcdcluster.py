# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

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

