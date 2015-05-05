from metaswitch.clearwater.cluster_manager.plugin_base import SynchroniserPluginBase
import logging

_log = logging.getLogger("example_plugin")


class ContentionDetectingPlugin(SynchroniserPluginBase):
    def __init__(self, ip):
        _log.debug("Raising not-clustered alarm")
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
        assert(nodes not in self.on_joining_nodes)
        self.on_joining_nodes.append(nodes)

    def on_new_cluster_config_ready(self, cluster_view):
        nodes = sorted(cluster_view.keys())
        assert(nodes not in self.on_new_cluster_config_ready_nodes)
        self.on_new_cluster_config_ready_nodes.append(nodes)

    def on_stable_cluster(self, cluster_view):
        nodes = sorted(cluster_view.keys())
        assert(nodes not in self.on_stable_cluster_nodes)
        self.on_stable_cluster_nodes.append(nodes)

    def on_leaving_cluster(self, cluster_view):
        nodes = sorted(cluster_view.keys())
        assert(nodes not in self.on_leaving_cluster_nodes)
        self.on_leaving_cluster_nodes.append(nodes)
