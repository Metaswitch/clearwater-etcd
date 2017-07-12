# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

from abc import ABCMeta, abstractmethod
import collections


PluginParams = collections.namedtuple(
                 'PluginParams',
                 ['ip', 'mgmt_ip', 'local_site', 'remote_site', 'remote_cassandra_seeds', 'signaling_namespace', 'uuid', 'etcd_key', 'etcd_cluster_key', 'cassandra_container_id'])


class SynchroniserPluginBase(object): # pragma: no cover
    __metaclass__ = ABCMeta

    @abstractmethod
    def key(self):

        """This should return the etcd key to use to monitor this cluster's
        state"""
        pass

    def cluster_description(self):
        """A brief description of the cluster managed by this plugin, for use in logs"""
        return "[unknown] cluster"

    def files(self):

        """This should return the files managed by this plugin,
        to avoid conflicts"""
        return []

    def should_be_in_cluster(self):

        """Allows a plugin to monitor, but not join, a remote cluster"""
        return True

    def on_startup(self, cluster_view):
        # Most of our plugins don't want to do anything on startup, so this
        # isn't marked as an @abstractmethod which they must implement.
        pass

    @abstractmethod
    def on_cluster_changing(self, cluster_view):

        """This hook is called when this node is already in the cluster, and the
        cluster is changing - whether growing or shrinking (and in future, it
        may be possible for elements to leave and join the cluster at the same
        time).

        This hook will generally update config files (e.g.
        /etc/clearwater/cluster_settings).

        This node will enter NORMAL_CONFIG_CHANGED state (or
        LEAVING_CONFIG_CHANGED, if this is the leaving node) immediately after
        this hook is called.

        """
        pass

    @abstractmethod
    def on_joining_cluster(self, cluster_view):

        """This hook is called when this node is about to join the cluster. It is
        the equivalent of the on_cluster_changing hook (which is called on
        existing nodes at the same time).

        This hook will generally update config files (e.g.
        /etc/clearwater/cluster_settings), as well as doing any other
        initialisation necessary on first joining a cluster.

        This node will enter JOINING_CONFIG_CHANGED state immediately after
        this hook is called.

        """
        pass

    @abstractmethod
    def on_new_cluster_config_ready(self, cluster_view):

        """This hook is called when all elements in the cluster have updated
        their config to reflect that the cluster is growing/shrinking (e.g.
        adding a new_servers line to /etc/clearwater/cluster_settings, or adding
        node/leaving lines to /etc/chronos/chronos.conf.

        This hook will generally run a resynchronisation process (like Astaire),
        if necessary.

        This node will enter NORMAL state immediately after this hook is called.

        """

        pass

    @abstractmethod
    def on_stable_cluster(self, cluster_view):

        """This hook is called when all elements in the cluster have finished
        any scaling-related work and returned to NORMAL state.

        This hook will generally update config files (e.g.
        /etc/clearwater/cluster_settings) to reflect the new cluster_view.

        This node will remain in NORMAL state after this hook is called.

        """

        pass

    @abstractmethod
    def on_leaving_cluster(self, cluster_view):

        """This hook is called when this node has left the cluster (e.g.
        streamed all its data away). It is the rough equivalent of the
        on_stable_cluster hook (which is subsequently called on the remaining
        nodes).

        This hook will generally do any cleanup necessary at this point (e.g.
        decommissioning Cassandra).

        This node will be in FINISHED state when the hook is called, and will
        not have a state after this hook is called (because it will be gone).

        """

        pass
