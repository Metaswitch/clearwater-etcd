# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

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
