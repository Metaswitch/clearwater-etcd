#!/usr/bin/python

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import consul
from time import sleep
import logging
from metaswitch.common import utils
from metaswitch.clearwater.etcd_shared.common_synchronizer import CommonSynchronizer

_log = logging.getLogger(__name__)

class CommonConsulSynchronizer(CommonSynchronizer):

    def __init__(self, plugin, ip, db_ip):
        super(CommonConsulSynchronizer, self).__init__(plugin)
        self._ip = ip

        self._client = consul.Consul(host=db_ip).kv

    # Read the state of the cluster from Consul (optionally waiting for a
    # changed state). Returns None if nothing could be read.
    def read_from_db(self, wait=True):
        result = None
        wait_index = None

        try:
            (wait_index, result) = self._client.get(self.key(), consistency=True)
            # FIXME: is this a string???
            wait_index=int(wait_index)
            wait_index += 1

            if wait:
                # If the cluster view hasn't changed since we last saw it, then
                # wait for it to change before doing anything else.
                _log.info("Read value {} from Consul, "
                          "comparing to last value {}".format(
                              utils.safely_encode(str(result)),
                              utils.safely_encode(self._last_value)))

                if result and result.get("Value") == self._last_value:
                    _log.info("Watching for changes with {}".format(wait_index))

                    (_, result) = self._client.get(self.key(),
                                                   wait=self.TIMEOUT_ON_WATCH,
                                                   index=wait_index,
                                                   recurse=False)

                    _log.debug("Finished watching")

                    # Return if we're terminating.
                    if self._terminate_flag:
                        return self.tuple_from_result(result)

                if result == None:
                    _log.info("Key {} doesn't exist in Consul yet".format(self.key()))
                    # Use any value on disk first, but the default value if not found
                    try:
                        f = open(self._plugin.file(), 'r')
                        value = f.read()  # pragma: no cover
                    except:
                        value = self.default_value()

                    # Attempt to create new key in Consul.
                    try:
                        # The `cas` set to 0 will fail the write if it finds a
                        # key already in Consul. This stops us overwriting a manually
                        # uploaded file with the default template.
                        self._client.put(self.key(), value, cas=0)
                        return (value, None)
                    except:  # pragma: no cover
                        _log.debug("Failed to create new key in the Consul store")
                        # Sleep briefly to avoid hammering a non-existent key
                        sleep(self.PAUSE_BEFORE_RETRY_ON_MISSING_KEY)
                        # Return 'None' so that plugins do not write config to disk
                        # that does not exist in the Consul store, leaving us out of sync
                        return (None, None)

        except Exception as e:
            # Catch-all error handler (for invalid requests, timeouts, etc -
            # start over.
            _log.error("{} caught {!r} when trying to read with index {}"
                       " - pause before retry".
                       format(self._ip, e, wait_index))
            # Sleep briefly to avoid hammering a failed server
            self.pause()
            # The main loop (which reads from Consul in a loop) should call this
            # function again after we return, causing the read to be retried.

        return self.tuple_from_result(result)

    # Calls read_from_db, and updates internal state to track the previously
    # seen value.
    #
    # The difference is:
    # - calling read_from_db twice will return the same value
    # - calling read_from_db twice will block on the second call until the
    # value changes
    #
    # Only the main thread should call update_from_db to avoid race conditions
    # or missed reads.
    def update_from_db(self):
        self._last_value, self._index = self.read_from_db(wait=True)
        return self._last_value

    def tuple_from_result(self, result):
        if result is None:
            return (None, None)
        # FIXME: re-enable this to support Consul for Queue Manger
        # elif self._abort_read is True:
        #     return (self._last_value, self._index)
        else:
            return (result.get("Value"), result.get("ModifyIndex"))
