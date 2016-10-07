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

"""Clearwater Queue Manager

Usage:
  main.py --local-ip=IP --local-site=SITE --etcd-key=KEY --node-type=TYPE
          [--foreground] [--log-level=LVL] [--log-directory=DIR] [--pidfile=FILE]
          [--wait-plugin-complete=RESP]

Options:
  -h --help                      Show this screen.
  --local-ip=IP                  IP address
  --local-site=NAME              Local site name
  --etcd-key=KEY                 Etcd key (top level)
  --node-type=TYPE               Node type (e.g. Sprout, AIO, ...)
  --foreground                   Don't daemonise
  --log-level=LVL                Level to log at, 0-4 [default: 3]
  --log-directory=DIR            Directory to log to [default: ./]
  --pidfile=FILE                 Pidfile to write [default: ./config-manager.pid]
  --wait-plugin-complete=RESP    Whether to wait for plugin responses

"""

from docopt import docopt, DocoptExit

from metaswitch.common import logging_config, utils
from metaswitch.clearwater.etcd_shared.plugin_loader import load_plugins_in_dir
from metaswitch.clearwater.queue_manager.plugin_base import PluginParams
from metaswitch.clearwater.queue_manager.etcd_synchronizer \
    import EtcdSynchronizer
from metaswitch.clearwater.queue_manager import pdlogs
import syslog
import logging
import os
import prctl

_log = logging.getLogger("queue_manager.main")

LOG_LEVELS = {'0': logging.ERROR,
              '1': logging.WARNING,
              # INFO-level logging is really useful, and not very spammy because
              # we're not on the call path, so produce INFO logs even at level 2
              '2': logging.INFO,
              '3': logging.INFO,
              '4': logging.DEBUG}

def main(args):
    syslog.openlog("queue-manager", syslog.LOG_PID)
    pdlogs.STARTUP.log()
    try:
        arguments = docopt(__doc__, argv=args)
    except DocoptExit:
        pdlogs.EXITING_BAD_CONFIG.log()
        raise

    local_ip = arguments['--local-ip']
    local_site = arguments['--local-site']
    etcd_key = arguments['--etcd-key']
    node_type = arguments['--node-type']
    log_dir = arguments['--log-directory']
    log_level = LOG_LEVELS.get(arguments['--log-level'], logging.DEBUG)
    wait_plugin_complete = arguments['--wait-plugin-complete']

    stdout_err_log = os.path.join(log_dir, "queue-manager.output.log")

    if not arguments['--foreground']:
        utils.daemonize(stdout_err_log)

    # Process names are limited to 15 characters, so abbreviate
    prctl.prctl(prctl.NAME, "cw-queue-mgr")

    logging_config.configure_logging(log_level, log_dir, "queue-manager", show_thread=True)

    # urllib3 logs a WARNING log whenever it recreates a connection, but our
    # etcd usage does this frequently (to allow watch timeouts), so deliberately
    # ignore this log
    urllib_logger = logging.getLogger('urllib3')
    urllib_logger.setLevel(logging.ERROR)

    utils.install_sigusr1_handler("queue-manager")

    # Drop a pidfile. We must keep a reference to the file object here, as this keeps
    # the file locked and provides extra protection against two processes running at
    # once.
    pidfile_lock = None
    try:
        pidfile_lock = utils.lock_and_write_pid_file(arguments['--pidfile']) # noqa
    except IOError:
        # We failed to take the lock - another process is already running
        exit(1)

    plugins_dir = "/usr/share/clearwater/clearwater-queue-manager/plugins/"
    plugins = load_plugins_in_dir(plugins_dir,
                                  PluginParams(wait_plugin_complete=wait_plugin_complete))
    plugins.sort(key=lambda x: x.key())
    threads = []

    for plugin in plugins:
        syncer = EtcdSynchronizer(plugin, local_ip, local_site, etcd_key, node_type)
        syncer.start_thread()

        threads.append(syncer.thread)
        _log.info("Loaded plugin %s" % plugin)

    while any([thr.isAlive() for thr in threads]):
        for thr in threads:
            if thr.isAlive():
                thr.join(1)

    _log.info("Clearwater Queue Manager shutting down")
    pdlogs.EXITING.log()
    syslog.closelog()
