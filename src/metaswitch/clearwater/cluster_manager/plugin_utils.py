import logging
import subprocess
from metaswitch.clearwater.cluster_manager import constants

_log = logging.getLogger("cluster_manager.plugin_utils")


def write_cluster_settings(filename, cluster_view):
    """Writes out the memcached cluster_settings file"""
    valid_servers_states = [constants.LEAVING_ACKNOWLEDGED_CHANGE,
                            constants.LEAVING_CONFIG_CHANGED,
                            constants.NORMAL_ACKNOWLEDGED_CHANGE,
                            constants.NORMAL_CONFIG_CHANGED,
                            constants.NORMAL]
    valid_new_servers_states = [constants.NORMAL,
                                constants.NORMAL_ACKNOWLEDGED_CHANGE,
                                constants.NORMAL_CONFIG_CHANGED,
                                constants.JOINING_ACKNOWLEDGED_CHANGE,
                                constants.JOINING_CONFIG_CHANGED]
    servers_ips = sorted(["{}:11211".format(k)
                          for k, v in cluster_view.iteritems()
                          if v in valid_servers_states])

    new_servers_ips = sorted(["{}:11211".format(k)
                              for k, v in cluster_view.iteritems()
                              if v in valid_new_servers_states])

    new_file_contents = ""
    if new_servers_ips == servers_ips:
        new_file_contents = "servers={}\n".format(",".join(servers_ips))
    else:
        new_file_contents = "servers={}\nnew_servers={}\n".format(
            ",".join(servers_ips),
            ",".join(new_servers_ips))

    _log.debug("Writing out cluster_settings file '{}'".format(
        new_file_contents))
    with open(filename, "w") as f:
        f.write(new_file_contents)


def run_command(command):
    """Runs the given shell command, logging the output and return code"""
    try:
        output = subprocess.check_output(command,
                                         shell=True,
                                         stderr=subprocess.STDOUT)
        _log.info("Command {} succeeded and printed output {!r}".
                  format(command, output))
        return 0
    except subprocess.CalledProcessError as e:
        _log.error("Command {} failed with return code {}"
                   " and printed output {!r}".format(command,
                                                     e.returncode,
                                                     e.output))
        return e.returncode
