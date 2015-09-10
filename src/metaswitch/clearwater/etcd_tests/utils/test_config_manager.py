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

from metaswitch.clearwater.config_manager import plugin_base
from metaswitch.clearwater.config_manager.etcd_synchronizer import EtcdSynchronizer as CfgEtcdSynchronizer
from threading import Condition

class DummyCfgPlugin(plugin_base.ConfigPluginBase):
    def __init__(self):
        self.value = None
        self.condvar = Condition()

    def key(self):
        return "/dummy/"

    def file(self):
        return "/dummy.json"

    def status(self, value):
        if value == self.value:
            return plugin_base.FileStatus.UP_TO_DATE
        elif self.value is None:
            return plugin_base.FileStatus.MISSING
        else:
            return plugin_base.FileStatus.OUT_OF_SYNC

    def on_config_changed(self, value, alarm):
        print "Config changed: {} -> {}".format(self.value, value)
        self.condvar.acquire()
        self.value = value
        self.condvar.notifyAll()
        self.condvar.release()

    def wait_for(self, expected, timeout=30):
        self.condvar.acquire()
        if self.value != expected:
            self.condvar.wait(timeout)
        self.condvar.release()


class TestConfigManager(object):
    def __init__(self, etcd_ip):
        self.plugin = DummyCfgPlugin()
        self.s = CfgEtcdSynchronizer(self.plugin, etcd_ip, "local", None)
        self.s.start_thread()

    def value(self):
        return self.plugin.value

    def wait_for(self, *args, **kwargs):
        self.plugin.wait_for(*args, **kwargs)

    def stop(self):
        self.s.terminate()



