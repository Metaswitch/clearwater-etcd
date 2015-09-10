#!/usr/bin/python

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

import etcd
from threading import Thread
from time import sleep

import logging

_log = logging.getLogger(__name__)


class CommonEtcdSynchronizer(object):
    def __init__(self, plugin, ip, pause_before_retry, etcd_ip=None):
        self._plugin = plugin
        self._ip = ip
        cxn_ip = etcd_ip or ip
        self._client = etcd.Client(cxn_ip, 4000)
        self._index = None
        self._last_value = None
        self._terminate_flag = False
        self.thread = Thread(target=self.main, name=self.thread_name())
        self._pause_before_retry = pause_before_retry

    def start_thread(self):
        self.thread.daemon = True
        self.thread.start()

    def terminate(self):
        self._terminate_flag = True
        self.thread.join()

    def pause(self):
        sleep(self._pause_before_retry)

    def main(self): pass

    def default_value(self):
        return None

    def is_running(self): return True

    def thread_name(self):
        return self._plugin.__class__.__name__

    # Read the state of the cluster from etcd (optionally waiting for a changed
    # state). Returns None if nothing could be read.
    def read_from_etcd(self, wait=True):
        result = None
        wait_index = None

        try:
            result = self._client.read(self.key(), quorum=True)
            wait_index = result.etcd_index+1

            if wait:
                # If the cluster view hasn't changed since we last saw it, then
                # wait for it to change before doing anything else.
                _log.info("Read value {} from etcd, "
                          "comparing to last value {}".format(
                              result.value,
                              self._last_value))
                if result.value == self._last_value:
                    _log.info("Watching for changes")
                    while not self._terminate_flag and self.is_running():
                        try:
                            _log.debug("Started a new watch")
                            result = self._client.read(self.key(),
                                                       wait=True,
                                                       waitIndex=wait_index,
                                                       timeout=5,
                                                       recursive=False)
                            break
                        except etcd.EtcdException as e:
                            if "Read timed out" in e.message:
                                # Timeouts after 5 seconds are expected, so
                                # ignore them - unless we're terminating, we'll
                                # stay in the while loop and try again
                                pass
                            else:
                                raise

                    _log.debug("Finished watching")

                    # Return if we're terminating.
                    if self._terminate_flag:
                        return self.tuple_from_result(result)

        except etcd.EtcdKeyError:
            _log.info("Key {} doesn't exist in etcd yet".format(self.key()))
            return (self.default_value(), None)
        except Exception as e:
            # Catch-all error handler (for invalid requests, timeouts, etc -
            # start over.
            _log.error("{} caught {!r} when trying to read with index {}"
                       " - pause before retry".
                       format(self._ip, e, wait_index))
            # Sleep briefly to avoid hammering a failed server
            self.pause()
            # The main loop (which reads from etcd in a loop) should call this
            # function again after we return, causing the read to be retried.

        return self.tuple_from_result(result)

    def tuple_from_result(self, result):
        if result is None:
            return (None, None)
        else:
            return (result.value, result.modifiedIndex)

    # Calls read_from_etcd, and updates internal state to track the previously
    # seen value.
    #
    # The difference is:
    # - calling read_from_etcd twice will return the same value
    # - calling update_from_etcd twice will block on the second call until the
    # value changes
    #
    # Only the main thread should call update_from_etcd to avoid race conditions
    # or missed reads.
    def update_from_etcd(self):
        self._last_value, self._index = self.read_from_etcd(wait=True)
        return self._last_value
