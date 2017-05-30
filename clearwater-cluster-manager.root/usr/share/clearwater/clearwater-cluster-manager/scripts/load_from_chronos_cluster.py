#! /usr/bin/python
# @file load_from_chronos_cluster.py
#
# Copyright (C) Metaswitch Networks 2016
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
site_name = sys.argv[2]
node_type = sys.argv[3]
etcd_key = sys.argv[4]

assert os.path.exists("/etc/init.d/chronos"), \
    "This script should be run on a node that's running Chronos"

etcd_key = "/{}/{}/{}/clustering/chronos".format(etcd_key, site_name, node_type)

with open('/etc/chronos/chronos_cluster.conf') as f:
    nodes = {}

    for line in f.readlines():
        line = line.strip().replace(' ','')
        if '=' in line:
            key, value = line.split("=")
            if key == "node":
                nodes[value] = "normal"
            elif key == "leaving":
                nodes[value] = "leaving"
            elif key == "joining":
                nodes[value] = "joining"

    data = json.dumps(nodes)

print "Inserting data %s into etcd key %s" % (data, etcd_key)

c = etcd.Client(local_ip, 4000)
new = c.write(etcd_key, data).value

if new == data:
    print "Update succeeded"
else:
    print "Update failed"
