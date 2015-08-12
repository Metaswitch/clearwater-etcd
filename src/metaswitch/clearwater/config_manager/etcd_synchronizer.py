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

from hashlib import md5

from .pdlogs import FILE_CHANGED
from metaswitch.clearwater.etcd_shared.common_etcd_synchronizer import CommonEtcdSynchronizer

import logging

_log = logging.getLogger("config_manager.etcd_synchronizer")


class EtcdSynchronizer(CommonEtcdSynchronizer):
    def __init__(self, plugin, ip, site, alarm):
        CommonEtcdSynchronizer.__init__(self, plugin, ip)
        self._site = site
        self._alarm = alarm

    def main(self):
        # Continue looping while the service is running.
        while not self._terminate_flag:
            # This blocks on changes to the watched key in etcd.
            _log.debug("Waiting for change from etcd for key {}".format(
                         self._plugin.key()))
            value = self.update_from_etcd()
            if self._terminate_flag:
                break

            if value:
                _log.info("Got new config value from etcd - filename {}, file size {}, MD5 hash {}".format(
                    self._plugin.file(),
                    len(value),
                    md5(value).hexdigest()))
                _log.debug("Got new config value from etcd:\n{}".format(value))
                self._plugin.on_config_changed(value, self._alarm)
                FILE_CHANGED.log(filename=self._plugin.file())

    def key(self):
        return "/clearwater/" + self._site + "/configuration/" + self._plugin.key()
