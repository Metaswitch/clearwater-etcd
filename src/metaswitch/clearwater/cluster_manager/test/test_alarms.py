#!/usr/bin/env python

import unittest
from mock import patch, call
from metaswitch.clearwater.cluster_manager.alarms import TooLongAlarm
from metaswitch.clearwater.cluster_manager.constants import RAISE_NOT_YET_CLUSTERED, CLEAR_NOT_YET_CLUSTERED
from time import sleep


class TestTooLongAlarm(unittest.TestCase):
    def setUp(self):
        pass

    @patch("metaswitch.clearwater.cluster_manager.alarms.issue_alarm")
    def test_raising(self, mock_issue_alarm):
        alarm = TooLongAlarm(0.1)
        alarm.trigger()
        sleep(0.3)
        self.assertIn(call(RAISE_NOT_YET_CLUSTERED), mock_issue_alarm.call_args_list)

    @patch("metaswitch.clearwater.cluster_manager.alarms.issue_alarm")
    def test_not_triggered_early(self, mock_issue_alarm):
        alarm = TooLongAlarm(0.1)
        alarm.trigger()
        self.assertEqual([], mock_issue_alarm.call_args_list)
        sleep(0.3)
        self.assertIn(call(RAISE_NOT_YET_CLUSTERED), mock_issue_alarm.call_args_list)

    @patch("metaswitch.clearwater.cluster_manager.alarms.issue_alarm")
    def test_cancellation(self, mock_issue_alarm):
        alarm = TooLongAlarm(0.1)
        alarm.trigger()
        alarm.cancel()

        sleep(0.3)
        self.assertNotIn(call(RAISE_NOT_YET_CLUSTERED), mock_issue_alarm.call_args_list)

    @patch("metaswitch.clearwater.cluster_manager.alarms.issue_alarm")
    def test_clearing(self, mock_issue_alarm):
        alarm = TooLongAlarm(0.1)
        alarm.trigger()
        sleep(0.3)
        alarm.cancel()

        self.assertEqual([call(RAISE_NOT_YET_CLUSTERED), call(CLEAR_NOT_YET_CLUSTERED)],
                          mock_issue_alarm.call_args_list)
