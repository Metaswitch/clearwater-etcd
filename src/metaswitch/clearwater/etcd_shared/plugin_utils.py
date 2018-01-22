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


def run_commands(list_of_command_args, namespace=None, log_error=True):
    """Runs the given shell commands in parallel, logging the output and return
    code.

    If a namespace is supplied the command is run in the specified namespace.

    Note that this runs the provided array of command arguments in a subprocess
    call without shell, to avoid shell injection. Ensure the command is passed 
    in as an array instead of a string.

    Returns 0 if all commands succeeded, and the return code of one of the
    failed commands otherwise.
    """
    namespace_prefix = ['ip', 'netns', 'exec', namespace] if namespace else []
    list_of_namespaced_command_args = [namespace_prefix + c for c in list_of_command_args]

    # Pass the close_fds argument to avoid the pidfile lock being held by
    # child processes
    processes = [(subprocess.Popen(c,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   close_fds=True), c)
                 for c in namespaced_command_args]

    error_returncodes = []
    for p, command_args in processes:
        stdout, stderr = p.communicate()
        # We log:
        # - everything (return code, stdout, stderr) in failure cases
        # - only stderr in success cases
        if p.returncode != 0:
            if log_error:
                _log.error("Command {} failed with return code {}\n"
                           "    stdout {!r}\n    stderr {!r}".format(' '.join(command_args),
                                                                     p.returncode,
                                                                     stdout,
                                                                     stderr))
            error_returncodes.append(p.returncode)
        else:
            if stderr:
                _log.warning("Command {} succeeded, with stderr output {!r}".
                             format(' '.join(command_args), stderr))
            else:
                _log.debug("Command {} succeeded".format(' '.join(command_args)))

    # Return 0, unless any nonzero return codes are present, in which case
    # arbitrarily return the first one.
    return next(error_returncodes, 0)


# Wrapper around run_commands which only runs a single command instead of
# multiple commands.
#
# It's structured this way because run_commands runs all the provided commands
# in parallel, and it's easier to have that as the standard function and then
# write a serial wrapper around it than the reverse.
def run_command(command_args, **kwargs):
    """Runs the given shell command. See run_commands for full documentation"""
    return run_commands([command_args], **kwargs)


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
