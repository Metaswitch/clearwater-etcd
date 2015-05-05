from .plugin_base import SynchroniserPluginBase


class NullPlugin(SynchroniserPluginBase):
    def __init__(self, key):
        self._key = key

    def key(self):
        return self._key

    def on_cluster_changing(self, cluster_view):
        pass

    def on_joining_cluster(self, cluster_view):
        pass

    def on_new_cluster_config_ready(self, cluster_view):
        pass

    def on_stable_cluster(self, cluster_view):
        pass

    def on_leaving_cluster(self, cluster_view):
        pass
