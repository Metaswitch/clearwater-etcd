# @file timers.py
#
# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

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
