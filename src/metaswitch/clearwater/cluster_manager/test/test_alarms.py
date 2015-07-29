#!/usr/bin/env python

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

import unittest
from mock import patch, call
from metaswitch.clearwater.cluster_manager.alarms import TooLongAlarm
from metaswitch.clearwater.cluster_manager.alarm_constants import \
    TOO_LONG_CLUSTERING_MINOR, TOO_LONG_CLUSTERING_CLEARED
from time import sleep


class TestTooLongAlarm(unittest.TestCase):
    def setUp(self):
        pass

    @patch("metaswitch.clearwater.cluster_manager.alarms.issue_alarm")
    def test_raising(self, mock_issue_alarm):
        alarm = TooLongAlarm(0.1)
        alarm.trigger("a")
        sleep(0.3)
        self.assertIn(call(TOO_LONG_CLUSTERING_MINOR), mock_issue_alarm.call_args_list)
        alarm.quit()

    @patch("metaswitch.clearwater.cluster_manager.alarms.issue_alarm")
    def test_not_triggered_early(self, mock_issue_alarm):
        alarm = TooLongAlarm(0.1)
        alarm.trigger("b")
        self.assertEqual([], mock_issue_alarm.call_args_list)
        sleep(0.3)
        self.assertIn(call(TOO_LONG_CLUSTERING_MINOR), mock_issue_alarm.call_args_list)
        alarm.quit()

    @patch("metaswitch.clearwater.cluster_manager.alarms.issue_alarm")
    def test_cancellation(self, mock_issue_alarm):
        alarm = TooLongAlarm(0.1)
        alarm.trigger("c")
        alarm.cancel()

        sleep(0.3)
        self.assertNotIn(call(TOO_LONG_CLUSTERING_MINOR), mock_issue_alarm.call_args_list)
        alarm.quit()

    @patch("metaswitch.clearwater.cluster_manager.alarms.issue_alarm")
    def test_clearing(self, mock_issue_alarm):
        alarm = TooLongAlarm(0.1)
        alarm.trigger("d")
        sleep(0.3)
        alarm.cancel()

        self.assertEqual([call(TOO_LONG_CLUSTERING_MINOR),
                          call(TOO_LONG_CLUSTERING_CLEARED)],
                          mock_issue_alarm.call_args_list)
        alarm.quit()
