# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


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

    tmp.write(contents.encode("utf-8"))

    os.chmod(tmp.name, permissions)

    os.rename(tmp.name, filename)
