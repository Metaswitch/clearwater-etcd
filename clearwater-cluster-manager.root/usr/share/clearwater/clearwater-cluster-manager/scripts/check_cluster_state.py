# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import sys
import etcd
import json

mgmt_node = sys.argv[1]
local_node = sys.argv[2]
local_site = sys.argv[3]
sites = sys.argv[4]
etcd_version = sys.argv[5]

client = etcd.Client(mgmt_node, 4000)

def describe_clusters():
    # Pull out all the clearwater keys.
    key = "/?recursive=True"

    try:
        result = client.get(key)
    except etcd.EtcdKeyNotFound:
        # There's no clearwater keys yet
        return

    cluster_values = {subkey.key: subkey.value for subkey in result.leaves}

    local_site_info = ""
    if sites != "" and etcd_version != "2.2.5":
        local_site_info = " in the local site (" + local_site + ")"

    print "This script prints out the status of the Chronos, Memcached and Cassandra clusters{}.\n".format(local_site_info)

    for (key, value) in sorted(cluster_values.items()):
        # Check if the key relates to clustering. The clustering key has the format
        # /clearwater*[</optional site name>]/<node type>/clustering/<store type>
        key_parts = key.split('/')

        if len(key_parts) > 5 and key_parts[4] == 'clustering':
            site = key_parts[2]
            node_type = key_parts[3]
            store_name = key_parts[5]
        elif len(key_parts) > 4 and key_parts[3] == 'clustering':
            site = ""
            node_type = key_parts[2]
            store_name = key_parts[4]
        else:
            # The key isn't to do with clustering, skip it
            continue

        if site != "" and sites != "" and etcd_version == "2.2.5":
            print "Describing the {} {} cluster in site {}:".format(node_type.capitalize(), store_name.capitalize(), site)
        else:
            print "Describing the {} {} cluster:".format(node_type.capitalize(), store_name.capitalize())

        cluster = json.loads(value)
        cluster_ok = all([state == "normal"
                          for node, state in cluster.iteritems()])

        if local_node in cluster:
            print "  The local node is in this cluster"
        else:
            print "  The local node is *not* in this cluster"

        if cluster_ok:
            print "  The cluster is stable"
        else:
            print "  The cluster is *not* stable"

        for node, state in cluster.iteritems():
            print "    {} is in state {}".format(node, state)
        print ""

describe_clusters()
