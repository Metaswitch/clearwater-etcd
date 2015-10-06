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

# This file contains code from the urllib3 project
# (https://github.com/shazow/urllib3) licensed under the MIT License:
#
# Copyright 2008-2014 Andrey Petrov and contributors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons
# to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or
# substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
# FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import etcd
from threading import Thread
from time import sleep
import logging

_log = logging.getLogger(__name__)


# Monkey patch urllib3 to close connections that time out.  Otherwise
# etcd will leak socket handles when we time out watches.
import urllib3
from contextlib import contextmanager
from socket import timeout as SocketTimeout
from urllib3.exceptions import ReadTimeoutError, ProtocolError
from urllib3.connection import HTTPException, BaseSSLError
@contextmanager
def _error_catcher(self): # pragma: no cover
    """
    Catch low-level python exceptions, instead re-raising urllib3
    variants, so that low-level exceptions are not leaked in the
    high-level api.
    On exit, release the connection back to the pool.
    """
    try:
        try:
            yield

        except SocketTimeout:
            # FIXME: Ideally we'd like to include the url in the ReadTimeoutError but
            # there is yet no clean way to get at it from this context.
            raise ReadTimeoutError(self._pool, None, 'Read timed out.')

        except BaseSSLError as e:
            # FIXME: Is there a better way to differentiate between SSLErrors?
            if 'read operation timed out' not in str(e):  # Defensive:
                # This shouldn't happen but just in case we're missing an edge
                # case, let's avoid swallowing SSL errors.
                raise

            raise ReadTimeoutError(self._pool, None, 'Read timed out.')

        except HTTPException as e:
            # This includes IncompleteRead.
            raise ProtocolError('Connection broken: %r' % e, e)
    except Exception:
        # The response may not be closed but we're not going to use it anymore
        # so close it now to ensure that the connection is released back to the pool.
        if self._original_response and not self._original_response.isclosed():
            self._original_response.close()

        # Before returning the socket, close it.  From the server's point of view, this
        # socket is in the middle of handling an SSL handshake/HTTP request so it we
        # were to try and re-use the connection later, we'd see undefined behaviour.
        #
        # Still return the connection to the pool (it will be re-established next time
        # it is used).
        self._connection.close()

        raise
    finally:
        if self._original_response and self._original_response.isclosed():
            self.release_conn()
urllib3.HTTPResponse._error_catcher = _error_catcher


class CommonEtcdSynchronizer(object):
    PAUSE_BEFORE_RETRY_ON_EXCEPTION = 30
    PAUSE_BEFORE_RETRY_ON_MISSING_KEY = 5
    TIMEOUT_ON_WATCH = 5

    def __init__(self, plugin, ip, etcd_ip=None):
        self._plugin = plugin
        self._ip = ip
        cxn_ip = etcd_ip or ip
        self._client = etcd.Client(cxn_ip, 4000)
        self._index = None
        self._last_value = None
        self._terminate_flag = False
        self.thread = Thread(target=self.main, name=self.thread_name())

    def start_thread(self):
        self.thread.daemon = True
        self.thread.start()

    def terminate(self):
        self._terminate_flag = True
        self.thread.join()

    def pause(self):
        sleep(self.PAUSE_BEFORE_RETRY_ON_EXCEPTION)

    def main(self): pass

    def default_value(self): return None

    def is_running(self): return True

    def thread_name(self): return self._plugin.__class__.__name__

    # Read the state of the cluster from etcd (optionally waiting for a changed
    # state). Returns None if nothing could be read.
    def read_from_etcd(self, wait=True):
        result = None
        wait_index = None

        try:
            result = self._client.read(self.key(), quorum=True)
            wait_index = result.etcd_index + 1

            if wait:
                # If the cluster view hasn't changed since we last saw it, then
                # wait for it to change before doing anything else.
                _log.info("Read value {} from etcd, "
                          "comparing to last value {}".format(
                              result.value,
                              self._last_value))

                if result.value == self._last_value:
                    _log.info("Watching for changes with {}".format(wait_index))

                    while not self._terminate_flag and self.is_running():
                        _log.debug("Started a new watch")
                        try:
                            result = self._client.read(self.key(),
                                                       timeout=self.TIMEOUT_ON_WATCH,
                                                       waitIndex=wait_index,
                                                       wait=True,
                                                       recursive=False)
                            break
                        except etcd.EtcdException as e:
                            if "Read timed out" in e.message:
                                # Timeouts after TIMEOUT_ON_WATCH seconds are expected, so
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
            # Sleep briefly to avoid hammering a non-existent key.
            sleep(self.PAUSE_BEFORE_RETRY_ON_MISSING_KEY)
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
