#!/usr/bin/env python

"""Clearwater Cluster Manager

Usage:
  main.py --local-ip=IP [--log-level=LVL] [--log-directory=DIR] [--pidfile=FILE]

Options:
  -h --help                   Show this screen.
  --local-ip=IP               IP address
  --log-level=LVL             Level to log at, 0-4 [default: 2]
  --log-directory=DIR         Directory to log to [default: ./]
  --pidfile=FILE              Pidfile to write [default: ./cluster-manager.pid]

"""

from docopt import docopt

from metaswitch.common import logging_config, utils
import logging
import os

LOG_LEVELS = {'0': logging.CRITICAL,
              '1': logging.ERROR,
              '2': logging.WARNING,
              '3': logging.INFO,
              '4': logging.DEBUG}

def main(args):
    arguments = docopt(__doc__, argv=args)

    listen_ip = arguments['--local-ip']
    log_dir = arguments['--log-directory']
    log_level = LOG_LEVELS.get(arguments['--log-level'], logging.INFO)

    stdout_err_log = os.path.join(log_dir, "cluster-manager.output.log")

    if not arguments['--foreground']:
        utils.daemonize(stdout_err_log)

    logging_config.configure_logging(log_level, log_dir, "cluster-manager")
    utils.install_sigusr1_handler("cluster-manager")
    
    # Drop a pidfile.
    pid = os.getpid()
    with open(arguments['--pidfile'], "w") as pidfile:
        pidfile.write(str(pid) + "\n")

if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
