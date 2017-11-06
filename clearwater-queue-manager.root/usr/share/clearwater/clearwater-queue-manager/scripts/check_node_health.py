#! /usr/bin/python

# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import os
import sys
import subprocess
from time import sleep
import logging

_log = logging.getLogger(__name__)


class Status:
    OK = 0
    WARN = 1
    ERROR = 2
    CRITICAL = 3


def check_status():
    try:
        output = subprocess.check_output(['monit', 'summary'])
    except subprocess.CalledProcessError as e:
        _log.error("Check_output of Monit summary failed: return code {},"
                   " printed output {!r}".format(e.returncode, e.output))
        return Status.CRITICAL

    result = Status.OK

    # Critical errors are those which must have been cleared for 30s before we
    # declare a node healthy
    critical_errors = [
        'Does not exist',
        'Initializing',
        'Data access error',
        'Execution failed',
        'Wait parent',
    ]

    # Errors are treated differently depending on the process/program that is
    # errored.
    # For uptime checking scripts, an error must have cleared before we declare
    # the node healthy, but don't need to have been cleared for 30s.
    # For other processes, errors must have been cleared for 30s before we
    # declare the node healthy
    errors = [
        'Uptime failed',
        'Status failed',
    ]

    successes = [
        'Running',
        'Status ok',
        'Waiting',
        'Not monitored',
    ]

    for line in output.split('\n'):
        line = line.strip()
        if line.endswith('Process') or line.endswith('Program'):
            if '_uptime' in line:
                # This program is just checking the uptime of another process
                # Critical errors put us in the CRITICAL state, but errors just
                # put us in the ERROR state
                if any(err in line for err in critical_errors):
                    result = Status.CRITICAL
                    break
                elif any(err in line for err in errors):
                    result = Status.ERROR
                elif not any(status in line for status in successes):
                    result = max(result, Status.WARN)
            else:
                # For this program, any errors are CRITICAL
                if (any(err in line for err in critical_errors) or
                    any(err in line for err in errors)):
                    result = Status.CRITICAL
                    break
                elif not any(status in line for status in successes):
                    result = max(result, Status.WARN)

    _log.debug("Current status is %s" % result)
    return result


def run_loop():
    # Seconds after which we return an error
    time_remaining = 450
    count_since_critical = 0

    while time_remaining:
        status = check_status()

        if status == Status.CRITICAL:
            count_since_critical = 0
        else:
            count_since_critical += 1

        # We require that all critical errors have been cleared for at least
        # 30s, and that there are no other errors
        if count_since_critical > 30 and status in (Status.OK, Status.WARN):
            return True

        sleep(1)
        time_remaining -= 1

    return False


if not os.getuid() == 0:
    _log.error("Insufficient permissions to run the check status script")
    sys.exit(1)

result = 0 if run_loop() is True else 1
sys.exit(result)
