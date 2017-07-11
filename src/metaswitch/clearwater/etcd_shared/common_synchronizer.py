#!/usr/bin/python

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

from threading import Thread
from time import sleep
import logging
import traceback
import os
import signal

_log = logging.getLogger(__name__)


class CommonSynchronizer(object):
    PAUSE_BEFORE_RETRY_ON_EXCEPTION = 30
    PAUSE_BEFORE_RETRY_ON_MISSING_KEY = 5
    TIMEOUT_ON_WATCH = 5

    def __init__(self, plugin):
        self._plugin = plugin
        self._index = None
        self._last_value = None

        # Set the terminate flag and the abort read flag to false initially
        # The terminate flag controls whether the synchronizer as a whole
        # should terminate, the abort flag ensures that any synchronizer
        # threads controlled by a futures is shut down fully
        self._terminate_flag = False
        self._abort_read = False
        self.thread = Thread(target=self.main_wrapper, name=self.thread_name())

    def start_thread(self):
        self.thread.daemon = True
        self.thread.start()

    def terminate(self):
        self._terminate_flag = True
        self.thread.join()

    def pause(self):
        sleep(self.PAUSE_BEFORE_RETRY_ON_EXCEPTION)

    def main_wrapper(self):
        # This function should be the entry point when we start an
        # EtcdSynchronizer thread. We use it to catch exceptions in main and
        # restart the whole process; if we didn't do this the thread would be
        # dead and we'd never notice.
        try:
            self.main()
        except Exception:  # pragma: no cover
            # Log the exception and send a SIGTERM to this process. If the
            # process needs to do anything before shutting down, it will have a
            # handler for catching the SIGTERM.
            _log.error(traceback.format_exc())
            os.kill(os.getpid(), signal.SIGTERM)

    def main(self):  # pragma: no cover
        pass

    def default_value(self):  # pragma: no cover
        return None

    def is_running(self):  # pragma: no cover
        return True

    def thread_name(self):
        return self._plugin.__class__.__name__
