#!/usr/bin/env python

"""Clearwater Cluster Manager

Usage:
  main.py --local-ip=IP [--foreground] [--log-level=LVL] [--log-directory=DIR] [--pidfile=FILE]

Options:
  -h --help                   Show this screen.
  --local-ip=IP               IP address
  --foreground                Don't daemonise
  --log-level=LVL             Level to log at, 0-4 [default: 3]
  --log-directory=DIR         Directory to log to [default: ./]
  --pidfile=FILE              Pidfile to write [default: ./cluster-manager.pid]

"""

from docopt import docopt

from metaswitch.common import logging_config, utils
from metaswitch.clearwater.cluster_manager.plugin_loader import load_plugins_in_dir
from metaswitch.clearwater.cluster_manager.etcd_synchronizer import EtcdSynchronizer
import logging
import os
from threading import Thread
import signal

_log = logging.getLogger("metaswitch.clearwater.cluster_manager.main")

LOG_LEVELS = {'0': logging.CRITICAL,
              '1': logging.ERROR,
              '2': logging.WARNING,
              '3': logging.INFO,
              '4': logging.DEBUG}


def install_sigquit_handler(plugins):
    def sigquit_handler(sig, stack):
        _log.debug("Handling SIGQUIT")
        for plugin in plugins:
            _log.debug("{} leaving cluster".format(plugin))
            plugin.leave_cluster()
    signal.signal(signal.SIGQUIT, sigquit_handler)


def main(args):
    arguments = docopt(__doc__, argv=args)

    listen_ip = arguments['--local-ip']
    log_dir = arguments['--log-directory']
    log_level = LOG_LEVELS.get(arguments['--log-level'], logging.DEBUG)

    stdout_err_log = os.path.join(log_dir, "cluster-manager.output.log")

    if not arguments['--foreground']:
        utils.daemonize(stdout_err_log)

    logging_config.configure_logging(log_level, log_dir, "cluster-manager")
    utils.install_sigusr1_handler("cluster-manager")

    # Drop a pidfile.
    pid = os.getpid()
    with open(arguments['--pidfile'], "w") as pidfile:
        pidfile.write(str(pid) + "\n")

    plugins_dir = "/usr/share/clearwater/clearwater-cluster-manager/plugins/"
    plugins = load_plugins_in_dir(plugins_dir, listen_ip)
    synchronizers = []
    threads = []
    for plugin in plugins:
        syncer = EtcdSynchronizer(plugin, listen_ip)
        thread = Thread(target=syncer.main)
        thread.daemon = True
        thread.start()

        synchronizers.append(syncer)
        threads.append(thread)
        _log.info("Loaded plugin %s" % plugin)

    install_sigquit_handler(synchronizers)

    while True:
        for thread in threads:
            thread.join(1)

if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
