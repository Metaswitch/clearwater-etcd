#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


import unittest
from mock import patch
from metaswitch.clearwater.config_manager.alarms import (
    ConfigAlarm, GLOBAL_CONFIG_NOT_SYNCHED)

class AlarmTest(unittest.TestCase):
    @patch("metaswitch.clearwater.config_manager.alarms.alarm_manager")
    def test_correct_alarm(self, mock_alarm_manager):
        ConfigAlarm(files=["/nonexistent"])
        mock_get_alarm = mock_alarm_manager.get_alarm
        mock_get_alarm.assert_called_once_with('config-manager',
                                               GLOBAL_CONFIG_NOT_SYNCHED)

    @patch("metaswitch.clearwater.config_manager.alarms.alarm_manager")
    def test_nonexistent_file(self, mock_alarm_manager):
        # Create a ConfigAlarm for a file that doesn't exist. The alarm should
        # be raised.
        a = ConfigAlarm(files=["/nonexistent"])

        # Check that the correct alarm is used.
        mock_get_alarm = mock_alarm_manager.get_alarm
        mock_get_alarm.assert_called_once_with('config-manager',
                                               GLOBAL_CONFIG_NOT_SYNCHED)

        mock_alarm = mock_get_alarm.return_value
        mock_alarm.set.assert_called_with()

        # Now create that file. The alarm should be cleared.
        a.update_file("/nonexistent")
        mock_alarm.clear.assert_called_with()

    @patch("metaswitch.clearwater.config_manager.alarms.alarm_manager")
    def test_existing_file(self, mock_alarm_manager):
        # Create a ConfigAlarm for a file that exists. The alarm should
        # immediately be cleared.
        ConfigAlarm(files=["/etc/passwd"])
        mock_alarm = mock_alarm_manager.get_alarm.return_value
        mock_alarm.clear.assert_called_once_with()
