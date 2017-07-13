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
from threading import Thread, Condition
from .alarm_constants import TOO_LONG_CLUSTERING
from metaswitch.common.alarms import alarm_manager

_log = logging.getLogger("cluster_manager.alarms")

ALARM_ISSUER_NAME = "cluster-manager"


class TooLongAlarm(object):
    def __init__(self, delay=(15*60)):
        self._condition = Condition()
        self._timer_thread = None
        self._should_alarm = False
        self._alarm = alarm_manager.get_alarm(ALARM_ISSUER_NAME,
                                              TOO_LONG_CLUSTERING)
        self._delay = delay

    def alarm(self):
        with self._condition:
            self._condition.wait(self._delay)
            if self._should_alarm:
                _log.info("Raising TOO_LONG_CLUSTERING alarm")
                self._alarm.set()

    def trigger(self, thread_name="Alarm thread"):
        self._should_alarm = True
        if self._timer_thread is None:
            _log.debug("TOO_LONG_CLUSTERING alarm triggered, will fire in {} seconds".format(self._delay))
            self._timer_thread = Thread(target=self.alarm, name=thread_name)
            self._timer_thread.start()

    def quit(self):
        if self._timer_thread is not None:
            self._should_alarm = False
            _log.info("TOO_LONG_CLUSTERING alarm cancelled when quitting")
            with self._condition:
                self._condition.notify()
            self._timer_thread.join()

    def cancel(self):
        with self._condition:
            self._should_alarm = False
            _log.info("TOO_LONG_CLUSTERING alarm cancelled")

            # cancel the thread
            self._condition.notify()
            self._timer_thread = None

            # clear the alarm
            self._alarm.clear()
