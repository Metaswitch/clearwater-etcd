# @file timers.py
#
# Project Clearwater - IMS in the Cloud
# Copyright (C) 2014  Metaswitch Networks Ltd
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

import logging
from threading import Thread, Condition

_log = logging.getLogger("queue_manager.timers")

class QueueTimer(object):
    def __init__(self, f):
        self._condition = Condition()
        self._timer_thread = None
        self.timer_popped = False
        self._timer_running = False
        self._delay = 1
        self.timer_id = "NO_ID"
        self._function_call = f

    def set_timer(self):
        with self._condition:
            self._condition.wait(self._delay)

            if self._timer_running:
                # Trigger FSM
                self.timer_popped = True
                self._timer_running = False
                if self._function_call:
                    self._function_call()

    def set(self, tid, delay):
        self.clear()
        self.timer_id = tid
        self.timer_popped = False
        self._timer_running = True
        self._delay = delay
        self._timer_thread = Thread(target=self.set_timer, name="Timer thread " + self.timer_id)
        self._timer_thread.start()

    def clear(self):
        if self._timer_thread is not None:
            self._timer_running = False
            with self._condition:
                self._condition.notify()
            self._timer_thread.join()
            self.timer_id = "NO_ID"
            self._timer_thread = None
