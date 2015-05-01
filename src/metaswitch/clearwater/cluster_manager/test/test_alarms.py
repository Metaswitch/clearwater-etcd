#!/usr/bin/env python

import unittest
from mock import patch, call
from metaswitch.clearwater.cluster_manager.alarms import TooLongAlarm
from metaswitch.clearwater.cluster_manager.constants import RAISE_TOO_LONG_CLUSTERING, CLEAR_TOO_LONG_CLUSTERING
from time import sleep


class TestTooLongAlarm(unittest.TestCase):
    def setUp(self):
        pass

    @patch("metaswitch.clearwater.cluster_manager.alarms.issue_alarm")
    def test_raising(self, mock_issue_alarm):
        alarm = TooLongAlarm(0.1)
        alarm.trigger("a")
        sleep(0.3)
        self.assertIn(call(RAISE_TOO_LONG_CLUSTERING), mock_issue_alarm.call_args_list)
        alarm.quit()

    @patch("metaswitch.clearwater.cluster_manager.alarms.issue_alarm")
    def test_not_triggered_early(self, mock_issue_alarm):
        alarm = TooLongAlarm(0.1)
        alarm.trigger("b")
        self.assertEqual([], mock_issue_alarm.call_args_list)
        sleep(0.3)
        self.assertIn(call(RAISE_TOO_LONG_CLUSTERING), mock_issue_alarm.call_args_list)
        alarm.quit()

    @patch("metaswitch.clearwater.cluster_manager.alarms.issue_alarm")
    def test_cancellation(self, mock_issue_alarm):
        alarm = TooLongAlarm(0.1)
        alarm.trigger("c")
        alarm.cancel()

        sleep(0.3)
        self.assertNotIn(call(RAISE_TOO_LONG_CLUSTERING), mock_issue_alarm.call_args_list)
        alarm.quit()

    @patch("metaswitch.clearwater.cluster_manager.alarms.issue_alarm")
    def test_clearing(self, mock_issue_alarm):
        alarm = TooLongAlarm(0.1)
        alarm.trigger("d")
        sleep(0.3)
        alarm.cancel()

        self.assertEqual([call(RAISE_TOO_LONG_CLUSTERING), call(CLEAR_TOO_LONG_CLUSTERING)],
                          mock_issue_alarm.call_args_list)
        alarm.quit()
