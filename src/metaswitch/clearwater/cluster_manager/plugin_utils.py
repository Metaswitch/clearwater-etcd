import logging
import os
import socket
import time
import signal
import yaml
from metaswitch.clearwater.cluster_manager import constants

_log = logging.getLogger("cluster_manager.plugin_utils")


def write_cluster_settings(filename, cluster_view):
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
    servers_ips = sorted([k for k, v in cluster_view.iteritems()
                          if v in valid_servers_states])

    new_servers_ips = sorted([k for k, v in cluster_view.iteritems()
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


def send_sighup(pidfile):
    pid = -1
    try:
        with open(pidfile) as f:
            pid = int(f.read())
    except IOError, ValueError:
        pass

    if pid != -1:
        os.kill(pid, signal.SIGHUP)
    else:
        _log.info("Reading PID from {} failed - process probably not running".format(pidfile))


# Edits cassandra.yaml and restarts Cassandra in order to join a Cassandra
# cluster. If there is an existing Cassandra cluster formed, we use the nodes in
# that cluster as the seeds; otherwise, we use the all the joining nodes as the
# seeds._
def join_cassandra_cluster(cluster_view, cassandra_yaml_file, ip):
    seeds_list = []

    for seed, state in cluster_view.items():
        if (state == constants.NORMAL_ACKNOWLEDGED_CHANGE or
            state == constants.NORMAL_CONFIG_CHANGED):
            seeds_list.append(seed)

    if len(seeds_list) == 0:
        for seed, state in cluster_view.items():
            if (state == constants.JOINING_ACKNOWLEDGED_CHANGE or
                state == constants.JOINING_CONFIG_CHANGED):
                seeds_list.append(seed)

    if len(seeds_list) > 0:
        seeds_list_str = ','.join(map(str, seeds_list))
        _log.info("Cassandra seeds list is {}".format(seeds_list_str))

        # Read cassandra.yaml.
        with open(cassandra_yaml_file) as f:
            doc = yaml.load(f)

        # Fill in the correct listen_address and seeds values in the yaml
        # document.
        doc["listen_address"] = ip
        doc["seed_provider"][0]["parameters"][0]["seeds"] = seeds_list_str

        # Write back to cassandra.yaml.
        with open(cassandra_yaml_file, "w") as f:
            yaml.dump(doc, f)

        # Restart Cassandra and make sure it picks up the new list of seeds.
        _log.debug("Restarting Cassandra")
        os.system("monit unmonitor cassandra")
        os.system("service cassandra stop")
        os.system("rm -rf /var/lib/cassandra/")
        os.system("mkdir -m 755 /var/lib/cassandra")
        os.system("chown -R cassandra /var/lib/cassandra")

        start_cassandra()

        _log.debug("Cassandra node successfully clustered")

    else:
        # Something has gone wrong - the local node should be WAITING_TO_JOIN in
        # etcd (at the very least).
        _log.warning("No Cassandra cluster defined in etcd - unable to join")


def leave_cassandra_cluster():
    # We need Cassandra to be running so that we can connect on port 9160 and
    # decommission it. Check if we can connect on port 9160.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("localhost", 9160))
    except:
        start_cassandra()

    os.system("nodetool decomission")
    _log.debug("Cassandra node successfully decommissioned")


def start_cassandra():
    os.system("service cassandra start")

    # Wait until we can connect on port 9160 - i.e. Cassandra is running.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            s.connect(("localhost", 9160))
            break
        except:
            time.sleep(1)
