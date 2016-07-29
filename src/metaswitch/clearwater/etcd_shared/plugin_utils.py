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


import tempfile
import os
from os.path import dirname
import subprocess
import logging

_log = logging.getLogger("etcd_shared.plugin_utils")


def run_command(command, namespace=None, log_error=True):
    """Runs the given shell command, logging the output and return code.

    If a namespace is supplied the command is run in the specified namespace.

    Note that this runs the provided command in a new shell, which will
    apply shell replacements.  Ensure the input string is sanitized before
    passing to this function.
    """
    if namespace:
        command = "ip netns exec {} ".format(namespace) + command

    # Pass the close_fds argument to avoid the pidfile lock being held by
    # child processes
    p = subprocess.Popen(command,
                         shell=True,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         close_fds=True)
    stdout, stderr = p.communicate()
    if p.returncode != 0:
        # it failed, log the return code and output
        if log_error:
            _log.error("Command {} failed with return code {}, "
                       "stdout {!r}, and stderr {!r}".format(command,
                                                             p.returncode,
                                                             stdout,
                                                             stderr))
            return p.returncode
    else:
        # it succeeded, log out stderr of the command run if present
        if stderr:
            _log.warning("Command {} succeeded, with stderr output {!r}".
                         format(command, stderr))
        else:
            _log.debug("Command {} succeeded".format(command))

        return 0


def safely_write(filename, contents, permissions=0644):
    """Writes a file without race conditions, by writing to a temporary file
    and then atomically renaming it"""

    # Create the temporary file in the same directory (to ensure it's on the
    # same filesystem and can be moved atomically), and don't automatically
    # delete it on close (os.rename deletes it).
    tmp = tempfile.NamedTemporaryFile(dir=dirname(filename), delete=False)

    tmp.write(contents)

    os.chmod(tmp.name, permissions)

    os.rename(tmp.name, filename)
