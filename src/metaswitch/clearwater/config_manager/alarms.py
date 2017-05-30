# @file alarms.py
#
# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


# This module provides a method for transporting alarm requests to a net-
# snmp alarm sub-agent for further handling. If the agent is unavailable,
# the request will timeout after 2 seconds and be dropped.


import logging
import os
from threading import Lock
from metaswitch.common.alarms import alarm_manager
from alarm_constants import GLOBAL_CONFIG_NOT_SYNCHED
from . import pdlogs

_log = logging.getLogger("config_manager.alarms")

ALARM_ISSUER_NAME = "config-manager"


class ConfigAlarm(object):
    def __init__(self, files=[]):
        self._files = {}
        self._alarm = alarm_manager.get_alarm(ALARM_ISSUER_NAME,
                                              GLOBAL_CONFIG_NOT_SYNCHED)
        self._lock = Lock()
        with self._lock:
            for file in files:
                self._files[file] = os.path.isfile(file)
            self.check_alarm()

    def update_file(self, filename):
        with self._lock:
            self._files[filename] = True;
            self.check_alarm()

    def check_alarm(self):
        if all(self._files.values()):
            self._alarm.clear()
        else:
            self._alarm.set()
            pdlogs.NO_SHARED_CONFIG_ALARM.log()
