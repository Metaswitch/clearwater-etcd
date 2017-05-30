# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.
from abc import ABCMeta, abstractmethod
import alarm_constants
import collections

PluginParams = collections.namedtuple(
                 'PluginParams',
                 ['wait_plugin_complete'])

class QueuePluginBase(object): # pragma : no cover
    __metaclass__ = ABCMeta

    # How long to wait for a node to do whatever it does while it's
    # at the front of the queue.
    WAIT_FOR_THIS_NODE = 480
    WAIT_FOR_OTHER_NODE = 480

    def local_alarm(self):
        return (alarm_constants.LOCAL_CONFIG_RESYNCHING,
                "local")

    def global_alarm(self):
        return (alarm_constants.GLOBAL_CONFIG_RESYNCHING,
                "global")

    @abstractmethod
    def key(self):
        """This should return the etcd key that holds the value managed by
        this plugin"""
        pass

    @abstractmethod
    def at_front_of_queue(self):
        """This hook is called when the node is at the front of the
        queue."""
        pass
