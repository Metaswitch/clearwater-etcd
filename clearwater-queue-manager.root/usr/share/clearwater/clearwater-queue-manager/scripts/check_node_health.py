#! /usr/bin/python

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
