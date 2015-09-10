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

from metaswitch.clearwater.cluster_manager.etcd_synchronizer import EtcdSynchronizer as ClusterEtcdSynchronizer
from metaswitch.clearwater.cluster_manager.plugin_base import SynchroniserPluginBase
from time import sleep

class DummyClusterPlugin(SynchroniserPluginBase):
    def __init__(self, fn):
        self.value = None
        self.fn = fn

    def key(self):
        return "/dummy/"

    def on_cluster_changing(self, cluster_view):
        self.value = cluster_view

    def on_joining_cluster(self, cluster_view):
        self.on_cluster_changing(cluster_view)

    def on_new_cluster_config_ready(self, cluster_view):
        if self.fn:
            self.fn()
            self.fn = None
        self.on_cluster_changing(cluster_view)

    def on_stable_cluster(self, cluster_view):
        self.on_cluster_changing(cluster_view)

    def on_leaving_cluster(self, cluster_view):
        self.on_cluster_changing(cluster_view)

    def wait_for(self, value, timeout=300):
        for i in range(timeout):
            if self.value != value:
                sleep(1)



class TestClusterManager(object):
    def __init__(self, etcd_ip, during_fn):
        self.plugin = DummyClusterPlugin(during_fn)
        self.s = ClusterEtcdSynchronizer(self.plugin, etcd_ip, pause_before_retry=2, fsm_delay=1)
        self.s.start_thread()

    def value(self):
        return self.plugin.value

    def wait_for(self, *args, **kwargs):
        self.plugin.wait_for(*args, **kwargs)

    def stop(self):
        self.s.terminate()



