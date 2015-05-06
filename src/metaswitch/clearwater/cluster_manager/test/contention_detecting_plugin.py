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

from metaswitch.clearwater.cluster_manager.plugin_base import SynchroniserPluginBase
import logging

_log = logging.getLogger("example_plugin")


class ContentionDetectingPlugin(SynchroniserPluginBase):
    """Plugin that asserts no method is called twice with the same arguments.

    This would mean that we were needlessly repeating work - our handling of
    etcd contention ought to avoid this."""
    def __init__(self, ip):
        self.ip = ip
        self.on_cluster_changing_nodes = []
        self.on_joining_nodes = []
        self.on_new_cluster_config_ready_nodes = []
        self.on_stable_cluster_nodes = []
        self.on_leaving_cluster_nodes = []

    def key(self):
        return "/test"

    def on_cluster_changing(self, cluster_view):
        nodes = sorted(cluster_view.keys())
        assert nodes not in self.on_cluster_changing_nodes,\
            "on_cluster_changing called twice with nodes {}".format(nodes)
        self.on_cluster_changing_nodes.append(nodes)

    def on_joining_cluster(self, cluster_view):
        nodes = sorted(cluster_view.keys())
        assert nodes not in self.on_joining_nodes,\
            "on_joining_cluster called twice with nodes {}".format(nodes)
        self.on_joining_nodes.append(nodes)

    def on_new_cluster_config_ready(self, cluster_view):
        nodes = sorted(cluster_view.keys())
        assert nodes not in self.on_new_cluster_config_ready_nodes,\
            "on_new_cluster_config_ready called twice with nodes {}".format(nodes)
        self.on_new_cluster_config_ready_nodes.append(nodes)

    def on_stable_cluster(self, cluster_view):
        nodes = sorted(cluster_view.keys())
        assert nodes not in self.on_stable_cluster_nodes,\
            "on_stable_cluster called twice with nodes {}".format(nodes)
        self.on_stable_cluster_nodes.append(nodes)

    def on_leaving_cluster(self, cluster_view):
        nodes = sorted(cluster_view.keys())
        assert nodes not in self.on_leaving_cluster_nodes,\
            "on_leaving_cluster called twice with nodes {}".format(nodes)
        self.on_leaving_cluster_nodes.append(nodes)
