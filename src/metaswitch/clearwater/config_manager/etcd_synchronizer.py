# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

from hashlib import sha512

from .pdlogs import FILE_CHANGED
from metaswitch.clearwater.etcd_shared.common_etcd_synchronizer import CommonEtcdSynchronizer
from metaswitch.common import utils
import logging

_log = logging.getLogger("config_manager.etcd_synchronizer")


class EtcdSynchronizer(CommonEtcdSynchronizer):
    def __init__(self, plugin, ip, site, alarm, key):
        super(EtcdSynchronizer, self).__init__(plugin, ip)
        self._site = site
        self._alarm = alarm
        self._key = key

    def main(self):
        # Continue looping while the service is running.
        while not self._terminate_flag:
            # This blocks on changes to the watched key in etcd.
            _log.debug("Waiting for change from etcd for key {}".format(
                         self._plugin.key()))
            old_value = self._last_value
            value = self.update_from_etcd()
            if self._terminate_flag:
                break

            if value and value != old_value:
                _log.info("Got new config value from etcd - filename {}, file size {}, SHA512 hash {}".format(
                    self._plugin.file(),
                    len(value),
                    sha512(utils.safely_encode(value)).hexdigest()))
                _log.debug("Got new config value from etcd:\n{}".format(
                           utils.safely_encode(value)))
                self._plugin.on_config_changed(value, self._alarm)
                FILE_CHANGED.log(filename=self._plugin.file())

    def key(self):
        return "/" + self._key + "/" + self._site + "/configuration/" + self._plugin.key()

    def default_value(self):
        return self._plugin.default_value()
