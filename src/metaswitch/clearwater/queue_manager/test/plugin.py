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
from metaswitch.clearwater.queue_manager.plugin_base import QueuePluginBase
from metaswitch.clearwater.queue_manager.etcd_synchronizer import WriteToEtcdStatus

class TestPlugin(QueuePluginBase):
    def key(self):
        return "queue_test"

    def at_front_of_queue(self):
        pass

class TestFrontOfQueueCallbackPlugin(QueuePluginBase):
    def __init__(self):
        self._at_front_of_queue_called = False

    def key(self):
        return "queue_test"

    def at_front_of_queue(self):
        self._at_front_of_queue_called = True

class TestNoTimerDelayPlugin(QueuePluginBase):
    def __init__(self):
        self.WAIT_FOR_OTHER_NODE = 0
        self.WAIT_FOR_THIS_NODE = 0

    def key(self):
        return "queue_test"

    def at_front_of_queue(self):
        pass

class TestFVPlugin(QueuePluginBase):
    def __init__(self, *args, **kwargs):
        super(TestFVPlugin, self).__init__(*args, **kwargs)
        self.at_front_of_queue_called = False
        self.front_of_queue_callback = None

    def key(self):
        return "queue_test"

    def when_at_front_of_queue(self, cb):
        self.front_of_queue_callback = cb

    def at_front_of_queue(self):
        self.at_front_of_queue_called = True
        rc = self.front_of_queue_callback()
        while rc != WriteToEtcdStatus.SUCCESS:
            rc = self.front_of_queue_callback()
