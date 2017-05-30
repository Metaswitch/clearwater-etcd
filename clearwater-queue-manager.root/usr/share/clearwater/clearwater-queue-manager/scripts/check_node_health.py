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
    CRITICAL = 2


def check_status():
    try:
        output = subprocess.check_output(['monit', 'summary'])
    except subprocess.CalledProcessError as e:
        _log.error("Check_output of Monit summary failed: return code {},"
                   " printed output {!r}".format(e.returncode, e.output))
        return Status.CRITICAL

    result = Status.OK
    critical_errors = [
        'Does not exist',
        'Initializing',
        'Data access error',
    ]
    warning_errors = [
        'Uptime failed',
    ]
    successes = [
        'Running',
        'Status ok',
        'Waiting',
        'Not monitored',
    ]

    for line in output.split('\n'):
        if line.startswith('Process') or line.startswith('Program'):
            if any(err in line for err in critical_errors):
                result = Status.CRITICAL
            elif any(err in line for err in warning_errors) or \
                    not any(status in line for status in successes):
                result = max(result, Status.WARN)
    _log.debug("Current status is %s" % result)
    return result


def run_loop():
    # Seconds after which we return an error
    time_remaining = 450
    success_count = 0

    while time_remaining:
        status = check_status()

        if status in (Status.OK, Status.WARN):
            success_count += 1

        if status == Status.CRITICAL:
            success_count = 0

        if success_count >= 30:
            return True

        sleep(1)
        time_remaining -= 1

    return False

if not os.getuid() == 0:
    _log.error("Insufficient permissions to run the check status script")
    sys.exit(1)

result = 0 if run_loop() is True else 1
sys.exit(result)
