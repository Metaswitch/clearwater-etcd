# Copyright (C) Metaswitch Networks 2015
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

from .plugin_base import SynchroniserPluginBase


class NullPlugin(SynchroniserPluginBase):
    def __init__(self, key):
        self._key = key

    def key(self):
        return self._key

    def on_cluster_changing(self, cluster_view):
        pass

    def on_joining_cluster(self, cluster_view):  # pragma: no cover
        pass

    def on_new_cluster_config_ready(self, cluster_view): # pragma: no cover
        pass

    def on_stable_cluster(self, cluster_view): # pragma: no cover
        pass

    def on_leaving_cluster(self, cluster_view):
        pass
