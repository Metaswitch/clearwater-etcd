#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

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
from time import sleep
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
    synchronizers = []
    threads = []

    for plugin in plugins:
        syncer = EtcdSynchronizer(plugin, local_ip, local_site, etcd_key, node_type)
        syncer.start_thread()

        synchronizers.append(syncer)
        threads.append(syncer.thread)
        _log.info("Loaded plugin %s" % plugin)

    utils.install_sigterm_handler(synchronizers)

    while any([thr.isAlive() for thr in threads]):
        for thr in threads:
            if thr.isAlive():
                thr.join(1)

    while not utils.should_quit:
        sleep(1)

    _log.info("Clearwater Queue Manager shutting down")
    pdlogs.EXITING.log()
    syslog.closelog()
