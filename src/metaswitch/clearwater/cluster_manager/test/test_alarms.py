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
