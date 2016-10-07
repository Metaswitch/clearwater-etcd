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
