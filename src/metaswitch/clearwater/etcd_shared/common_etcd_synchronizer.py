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
from functools import wraps
import logging
import traceback
import os
import signal
from metaswitch.common import utils

_log = logging.getLogger(__name__)


# Monkey patch urllib3 to close connections that time out.  Otherwise
# etcd will leak socket handles when we time out watches.
import urllib3
from contextlib import contextmanager
from socket import timeout as SocketTimeout
from socket import error as SocketError
from urllib3.exceptions import ReadTimeoutError, ProtocolError, MaxRetryError, HTTPError
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

# Monkeypatch python-etcd to catch MaxRetryErrors. This is a hacky fix to cover
# https://github.com/jplana/python-etcd/issues/160 (it doesn't cover why
# urllib3 is hitting a MaxRetryError in the first place). We should remove this
# if we update the python-etcd version.
# The change in this code (see the PATCHED section below) is to catch
# MaxRetryErrors and convert them to EtcdWatchTimedOut errors - this stops a
# worrying error log evey 5 seconds. No other code has been changed (the
# api* functions are only included in this patch so that they can be decorated
# with our patched decorator).
def _patched_wrap_request(payload): # pragma: no cover
    @wraps(payload)
    def wrapper(self, path, method, params=None, timeout=None):
        some_request_failed = False
        response = False

        if timeout is None:
            timeout = self.read_timeout

        if timeout == 0:
            timeout = None

        if not path.startswith('/'):
            raise ValueError('Path does not start with /')

        while not response:
            try:
                response = payload(self, path, method,
                                   params=params, timeout=timeout)
                # Check the cluster ID hasn't changed under us.  We use
                # preload_content=False above so we can read the headers
                # before we wait for the content of a watch.
                self._check_cluster_id(response)
                # Now force the data to be preloaded in order to trigger any
                # IO-related errors in this method rather than when we try to
                # access it later.
                _ = response.data # noqa
                # urllib3 doesn't wrap all httplib exceptions and earlier versions
                # don't wrap socket errors either.
            except (HTTPError, MaxRetryError, HTTPException, SocketError) as e:
                # PATCHED
                if (isinstance(params, dict) and
                    params.get("wait") == "true" and
                    (isinstance(e,
                                urllib3.exceptions.MaxRetryError) or
                     isinstance(e,
                                urllib3.exceptions.ReadTimeoutError))):
                    _log.debug("Watch timed out.")
                    raise etcd.EtcdWatchTimedOut(
                        "Watch timed out: %r" % e,
                        cause=e
                    )
                _log.error("Request to server %s failed: %r",
                           self._base_uri, e)

                if self._allow_reconnect:
                    _log.info("Reconnection allowed, looking for another "
                              "server.")
                    # _next_server() raises EtcdException if there are no
                    # machines left to try, breaking out of the loop.
                    self._base_uri = self._next_server(cause=e)
                    some_request_failed = True
                    # if exception is raised on _ = response.data
                    # the condition for while loop will be False
                    # but we should retry
                    response = False
                else:
                    _log.debug("Reconnection disabled, giving up.")
                    raise etcd.EtcdConnectionFailed(
                        "Connection to etcd failed due to %r" % e,
                        cause=e
                    )
            except etcd.EtcdClusterIdChanged as e:
                _log.warning(e)
                raise
            except:
                _log.exception("Unexpected request failure, re-raising.")
                raise

            if some_request_failed:
                if not self._use_proxies:
                    # The cluster may have changed since last invocation
                    self._machines_cache = self.machines
                self._machines_cache.remove(self._base_uri)
        return self._handle_server_response(response)
    return wrapper

@_patched_wrap_request
def api_execute_json_with_patched_decorator(self, path, method, params=None, timeout=None): # pragma: no cover
    url = self._base_uri + path
    json_payload = json.dumps(params) # noqa
    headers = self._get_headers()
    headers['Content-Type'] = 'application/json'
    return self.http.urlopen(method,
                             url,
                             body=json_payload,
                             timeout=timeout,
                             redirect=self.allow_redirect,
                             headers=headers,
                             preload_content=False)
etcd.Client.api_execute_json = api_execute_json_with_patched_decorator

@_patched_wrap_request
def api_execute_with_patched_decorator(self, path, method, params=None, timeout=None): # pragma: no cover
    """ Executes the query. """
    url = self._base_uri + path
    if (method == self._MGET) or (method == self._MDELETE):
        return self.http.request(
            method,
            url,
            timeout=timeout,
            fields=params,
            redirect=self.allow_redirect,
            headers=self._get_headers(),
            preload_content=False)

    elif (method == self._MPUT) or (method == self._MPOST):
        return self.http.request_encode_body(
            method,
            url,
            fields=params,
            timeout=timeout,
            encode_multipart=False,
            redirect=self.allow_redirect,
            headers=self._get_headers(),
            preload_content=False)
    else:
        raise etcd.EtcdException(
            'HTTP method {} not supported'.format(method))
etcd.Client.api_execute = api_execute_with_patched_decorator

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

    def main_wrapper(self): # pragma: no cover
        # This function should be the entry point when we start an
        # EtcdSynchronizer thread. We use it to catch exceptions in main and
        # restart the whole process; if we didn't do this the thread would be
        # dead and we'd never notice.
        try:
            self.main()
        except Exception:
            # Log the exception and send a SIGTERM to this process. If the
            # process needs to do anything before shutting down, it will have a
            # handler for catching the SIGTERM.
            _log.error(traceback.format_exc())
            os.kill(os.getpid(), signal.SIGTERM)

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
                              utils.safely_encode(result.value),
                              utils.safely_encode(self._last_value)))

                if result.value == self._last_value:
                    _log.info("Watching for changes with {}".format(wait_index))

                    while not self._terminate_flag and not self._abort_read and self.is_running():
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
        elif self._abort_read is True:
            return (self._last_value, self._index)
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
