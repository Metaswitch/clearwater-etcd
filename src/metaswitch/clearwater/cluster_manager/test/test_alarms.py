#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import unittest
from mock import patch
from metaswitch.clearwater.cluster_manager.alarms import TooLongAlarm
from metaswitch.clearwater.cluster_manager.alarm_constants import \
    TOO_LONG_CLUSTERING
from time import sleep


class TestTooLongAlarm(unittest.TestCase):

    @patch("metaswitch.clearwater.cluster_manager.alarms.alarm_manager")
    def test_correct_alarm(self, mock_alarm_manager):
        alarm = TooLongAlarm(0.1)
        mock_get_alarm = mock_alarm_manager.get_alarm
        mock_get_alarm.assert_called_once_with('cluster-manager',
                                               TOO_LONG_CLUSTERING)
        alarm.quit()

    @patch("metaswitch.clearwater.cluster_manager.alarms.alarm_manager")
    def test_raising(self, mock_alarm_manager):
        alarm = TooLongAlarm(0.1)
        alarm.trigger("a")
        sleep(0.3)

        mock_alarm = mock_alarm_manager.get_alarm.return_value
        mock_alarm.set.assert_called_once_with()
        alarm.quit()

    @patch("metaswitch.clearwater.cluster_manager.alarms.alarm_manager")
    def test_not_triggered_early(self, mock_alarm_manager):
        mock_alarm = mock_alarm_manager.get_alarm.return_value

        alarm = TooLongAlarm(0.1)
        alarm.trigger("b")
        self.assertEqual([], mock_alarm.set.call_args_list)
        sleep(0.3)

        mock_alarm.set.assert_called_once_with()
        alarm.quit()

    @patch("metaswitch.clearwater.cluster_manager.alarms.alarm_manager")
    def test_cancellation(self, mock_alarm_manager):
        alarm = TooLongAlarm(0.1)
        alarm.trigger("c")
        alarm.cancel()

        sleep(0.3)

        mock_alarm = mock_alarm_manager.get_alarm.return_value
        mock_alarm.clear.assert_called_once_with()
        alarm.quit()

    @patch("metaswitch.clearwater.cluster_manager.alarms.alarm_manager")
    def test_clearing(self, mock_alarm_manager):
        alarm = TooLongAlarm(0.1)
        alarm.trigger("d")
        sleep(0.3)
        alarm.cancel()

        mock_alarm = mock_alarm_manager.get_alarm.return_value
        mock_alarm.set.assert_called_once_with()
        mock_alarm.clear.assert_called_once_with()
        alarm.quit()
