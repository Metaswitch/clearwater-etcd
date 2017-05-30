# Copyright (C) Metaswitch Networks 2015
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


from metaswitch.clearwater.cluster_manager.plugin_base import SynchroniserPluginBase
import logging

_log = logging.getLogger("example_plugin")

class DummyPlugin(SynchroniserPluginBase):
    def __init__(self, params):
        _log.debug("Raising not-clustered alarm")

    def key(self):
        return "/test"

    def on_cluster_changing(self, cluster_view):
        _log.debug("New view of the cluster is {}".format(cluster_view))

    def on_joining_cluster(self, cluster_view):
        _log.info("I'm about to join the cluster")

    def on_new_cluster_config_ready(self, cluster_view):
        _log.info("All nodes have updated configuration")

    def on_stable_cluster(self, cluster_view):
        _log.info("Cluster is stable")
        _log.debug("Clearing not-clustered alarm")

    def on_leaving_cluster(self, cluster_view):
        _log.info("I'm out of the cluster")

class DummyWatcherPlugin(DummyPlugin):
    def __init__(self, params):
        super(DummyWatcherPlugin, self).__init__(params)
        self.on_stable_cluster_called = False

    def on_stable_cluster(self, cluster_view):
        self.on_stable_cluster_called = True

    def should_be_in_cluster(self):
        return False
