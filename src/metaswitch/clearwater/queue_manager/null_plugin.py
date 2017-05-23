# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

from .plugin_base import QueuePluginBase


class NullPlugin(QueuePluginBase):
    def __init__(self, key):
        self._key = key

    def key(self):
        return self._key

    def at_front_of_queue(self):
        pass
