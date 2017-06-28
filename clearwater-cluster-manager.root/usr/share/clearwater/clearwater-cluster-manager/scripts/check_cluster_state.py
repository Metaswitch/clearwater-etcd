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

mgmt_node = sys.argv[1]
local_node_ip = sys.argv[2]
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
    cluster_values = {key: cluster_values[key] for key in sorted(cluster_values)}    

    local_site_info = ""
    if sites != "" and etcd_version != "2.2.5":
        local_site_info = " in the local site (" + local_site + ")"

    # Put the cluster name in alphabetical order
    print "This script prints the status of the Cassandra, Chronos, and Memcached clusters{}.".format(local_site_info)

    plugin_dir = '/usr/share/clearwater/clearwater-cluster-manager/plugins'
    if os.path.isdir(plugin_dir):
        plugins = [(plugin_name[:-10]).capitalize() for plugin_name in os.listdir(plugin_dir) if
                plugin_name.endswith('_plugin.py')]

        # Memcached_remote is now deprecated with the new GR support
        if 'Memcached_remote' in plugins:
            plugins.remove('Memcached_remote')
        
        plugins.sort()

        if len(plugins) >= 2:
            cluster_str = "{} and {} clusters".format(", ".join(plugins[:-1]),
                    plugins[-1])
        else:
            cluster_str = str(plugins[0]) + " cluster"

        print "This node ({}) should be in the {}.\n".format(local_node_ip,
                cluster_str)
    else:
        print "This node ({}) should not be in any cluster.\n".format(local_node_ip)

    for (key, value) in cluster_values.items():
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
            print "Describing the {} cluster in site {}:".format(store_name.capitalize(), site)
        else:
            print "Describing the {} cluster:".format(store_name.capitalize())

        cluster = json.loads(value)
        cluster_ok = all([state == "normal"
                          for node, state in cluster.iteritems()])

        if cluster_ok:
            print "  The cluster is stable"
        else:
            print "  The cluster is *not* stable"

        for node, state in cluster.iteritems():
            print "    {} is in state {}".format(node, state)
        print ""

describe_clusters()
