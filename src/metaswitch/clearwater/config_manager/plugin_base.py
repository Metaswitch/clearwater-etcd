# Project Clearwater - IMS in the Cloud
# Copyright (C) 2015 Metaswitch Networks Ltd
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version, along with the "Special Exception" for use of
# the program along with SSL, set forth below. This program is distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details. You should have received a copy of the GNU General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
# The author can be reached by email at clearwater@metaswitch.com or by
# post at Metaswitch Networks Ltd, 100 Church St, Enfield EN2 6BQ, UK
#
# Special Exception
# Metaswitch Networks Ltd  grants you permission to copy, modify,
# propagate, and distribute a work formed by combining OpenSSL with The
# Software, or a work derivative of such a combination, even if such
# copying, modification, propagation, or distribution would otherwise
# violate the terms of the GPL. You must comply with the GPL in all
# respects for all of the code used other than OpenSSL.
# "OpenSSL" means OpenSSL toolkit software distributed by the OpenSSL
# Project and licensed under the OpenSSL Licenses, or a work based on such
# software and licensed under the OpenSSL Licenses.
# "OpenSSL Licenses" means the OpenSSL License and Original SSLeay License
# under which the OpenSSL Project distributes the OpenSSL toolkit software,
# as those licenses appear in the file LICENSE-OPENSSL.
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
