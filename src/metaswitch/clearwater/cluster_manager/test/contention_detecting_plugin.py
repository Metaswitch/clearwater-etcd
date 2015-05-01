from metaswitch.clearwater.cluster_manager.plugin_base import SynchroniserPluginBase
import logging

_log = logging.getLogger("example_plugin")


class ContentionDetectingPlugin(SynchroniserPluginBase):
    def __init__(self):
        _log.debug("Raising not-clustered alarm")
        self.has_written_intermediate_config = False
        self.has_written_final_config = False
        self.has_started_resync = False
        self.has_decommissioned = False

    def key(self):
        return "/test"

    def on_cluster_changing(self, cluster_view):
        assert not self.has_written_intermediate_config
        assert not self.has_written_final_config
        assert not self.has_started_resync
        assert not self.has_decommissioned
        _log.debug("New view of the cluster is {}".format(cluster_view))
        self.has_written_intermediate_config = True

    def on_joining_cluster(self, cluster_view):
        assert not self.has_written_intermediate_config
        assert not self.has_written_final_config
        assert not self.has_started_resync
        assert not self.has_decommissioned
        _log.info("I'm about to join the cluster")
        self.has_written_intermediate_config = True

    def on_new_cluster_config_ready(self, cluster_view):
        assert self.has_written_intermediate_config
        assert not self.has_written_final_config
        assert not self.has_started_resync
        assert not self.has_decommissioned
        _log.info("All nodes have updated configuration")
        self.has_started_resync = True

    def on_stable_cluster(self, cluster_view):
        assert self.has_written_intermediate_config
        assert not self.has_written_final_config
        assert self.has_started_resync
        assert not self.has_decommissioned
        _log.info("Cluster is stable")
        _log.debug("Clearing not-clustered alarm")
        self.has_written_final_config = True

    def on_leaving_cluster(self, cluster_view):
        assert self.has_written_intermediate_config
        assert not self.has_written_final_config
        assert self.has_started_resync
        assert not self.has_decommissioned
        _log.info("I'm out of the cluster")
        self.has_decommissioned = True

