# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.
from abc import ABCMeta, abstractmethod

class FileStatus:
    UP_TO_DATE = 0
    OUT_OF_SYNC = 1
    MISSING = 2

class ConfigPluginBase(object): # pragma : no cover
    __metaclass__ = ABCMeta

    @abstractmethod
    def key(self):
        """This should return the etcd key that holds the config managed by
        this plugin"""
        pass

    @abstractmethod
    def file(self):
        """This should return the name of the file on disk that is managed
        by this plugin."""
        pass

    @abstractmethod
    def default_value(self):
        """This should return the default empty value for the file on disk
        that is managed by this plugin."""
        pass

    @abstractmethod
    def status(self, value):
        """This should report the status of the file using the FileStatus enum
        values."""
        pass

    @abstractmethod
    def on_config_changed(self, value, alarm):
        """This hook is called when the key that controls this plugin's config
        changes.  This hook should update associated configuration files and
        restart any processes needed in order to apply the change.  The hook
        should also report the status of the controlled file to the alarm
        manager."""
        pass
