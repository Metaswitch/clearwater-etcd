# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

from metaswitch.common.alarms import alarm_manager, MINOR, CRITICAL
import logging

_log = logging.getLogger("queue_manager.alarms")

ALARM_ISSUER_NAME = "queue-manager"


class QueueAlarm(object):
    def __init__(self, alarm_handle, name):
        self._alarm = alarm_manager.get_alarm(ALARM_ISSUER_NAME,
                                              alarm_handle)
        self._name = name

    def clear(self):
        _log.debug("Clearing %s alarm" % self._name)
        self._alarm.clear()

    def minor(self):
        _log.debug("Raising minor %s alarm" % self._name)
        self._alarm.set(MINOR)

    def critical(self):
        _log.debug("Raising critical %s alarm" % self._name)
        self._alarm.set(CRITICAL)
