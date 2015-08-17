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

"""Clearwater Config Manager

Usage:
  main.py --local-ip=IP --local-site=SITE --etcd-key=KEY [--foreground]
          [--log-level=LVL] [--log-directory=DIR] [--pidfile=FILE]

Options:
  -h --help                   Show this screen.
  --local-ip=IP               IP address
  --local-site=NAME           Local site name
  --etcd-key=KEY              Etcd key (top level)
  --foreground                Don't daemonise
  --log-level=LVL             Level to log at, 0-4 [default: 3]
  --log-directory=DIR         Directory to log to [default: ./]
  --pidfile=FILE              Pidfile to write [default: ./config-manager.pid]

"""

from docopt import docopt, DocoptExit

from metaswitch.common import logging_config, utils
from metaswitch.clearwater.etcd_shared.plugin_loader \
    import load_plugins_in_dir
from metaswitch.clearwater.config_manager.etcd_synchronizer \
    import EtcdSynchronizer
from metaswitch.clearwater.config_manager.alarms \
    import ConfigAlarm
from metaswitch.clearwater.config_manager import pdlogs
import syslog
import logging
import os
from threading import Thread

_log = logging.getLogger("config_manager.main")

LOG_LEVELS = {'0': logging.ERROR,
              '1': logging.WARNING,
              # INFO-level logging is really useful, and not very spammy because
              # we're not on the call path, so produce INFO logs even at level 2
              '2': logging.INFO,
              '3': logging.INFO,
              '4': logging.DEBUG}

def main(args):
    syslog.openlog("config-manager", syslog.LOG_PID)
    pdlogs.STARTUP.log()
    try:
        arguments = docopt(__doc__, argv=args)
    except DocoptExit:
        pdlogs.EXITING_BAD_CONFIG.log()
        raise

    local_ip = arguments['--local-ip']
    local_site = arguments['--local-site']
    etcd_key = arguments['--etcd-key']
    log_dir = arguments['--log-directory']
    log_level = LOG_LEVELS.get(arguments['--log-level'], logging.DEBUG)

    stdout_err_log = os.path.join(log_dir, "config-manager.output.log")

    if not arguments['--foreground']:
        utils.daemonize(stdout_err_log)

    logging_config.configure_logging(log_level, log_dir, "config-manager", show_thread=True)

    # urllib3 logs a WARNING log whenever it recreates a connection, but our
    # etcd usage does this frequently (to allow watch timeouts), so deliberately
    # ignore this log
    urllib_logger = logging.getLogger('urllib3')
    urllib_logger.setLevel(logging.ERROR)

    utils.install_sigusr1_handler("config-manager")

    # Drop a pidfile.
    pid = os.getpid()
    with open(arguments['--pidfile'], "w") as pidfile:
        pidfile.write(str(pid) + "\n")

    plugins_dir = "/usr/share/clearwater/clearwater-config-manager/plugins/"
    plugins = load_plugins_in_dir(plugins_dir)
    plugins.sort(key=lambda x: x.key())
    threads = []

    files = [p.file() for p in plugins]
    alarm = ConfigAlarm(files)

    for plugin in plugins:
        syncer = EtcdSynchronizer(plugin, local_ip, local_site, alarm, etcd_key)
        thread = Thread(target=syncer.main, name=plugin.__class__.__name__)
        thread.start()

        threads.append(thread)
        _log.info("Loaded plugin %s" % plugin)

    while any([thr.isAlive() for thr in threads]):
        for thr in threads:
            if thr.isAlive():
                thr.join(1)

    _log.info("Clearwater Configuration Manager shutting down")
    pdlogs.EXITING.log()
    syslog.closelog()
