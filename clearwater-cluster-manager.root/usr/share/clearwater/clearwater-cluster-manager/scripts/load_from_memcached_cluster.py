# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import sys
import etcd
import json
import os

local_ip = sys.argv[1]
local_site = sys.argv[2]
remote_site = sys.argv[3]
node_type = sys.argv[4]
etcd_key = sys.argv[5]

assert os.path.exists("/etc/init.d/clearwater-memcached"), \
    "This script should be run on a node that's running Memcached"

local_etcd_key = "/{}/{}/{}/clustering/memcached".format(etcd_key,
                                                         local_site,
                                                         node_type)
remote_etcd_key = "/{}/{}/{}/clustering/memcached".format(etcd_key,
                                                          remote_site,
                                                          node_type)

def strip_port(server):
    return server.rsplit(":", 1)[0].strip()

c = etcd.Client(local_ip, 4000)


def load_file_into_etcd(filename, etcd_key):
    with open(filename) as f:
        nodes = {}

        for line in f.readlines():
            if '=' in line:
                key, value = line.split("=")
                if key == "servers":
                    for server in value.split(","):
                        nodes[strip_port(server)] = "normal"
                elif key == "new_servers":
                    for server in value.split(","):
                        nodes[strip_port(server)] = "joining"

        data = json.dumps(nodes)

    print "Inserting data %s into etcd key %s" % (data, etcd_key)

    new = c.write(etcd_key, data).value

    if new == data:
        print "Update succeeded"
    else:
        print "Update failed"

load_file_into_etcd('/etc/clearwater/cluster_settings', local_etcd_key)

if remote_site != "":
    load_file_into_etcd('/etc/clearwater/remote_cluster_settings', remote_etcd_key)
