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

client = etcd.Client(mgmt_node, 4000)


def describe_clusters():
    """This function returns the the number of unstable clusters it is
     checking """
    # Pull out all the clearwater keys.
    key = "/?recursive=True"

    try:
        result = client.get(key)
    except etcd.EtcdKeyNotFound:
        # There's no clearwater keys yet
        return

    cluster_values = {subkey.key: subkey.value for subkey in result.leaves}

    local_site_info = ""
    if sites != "" and local_site != sites:
        local_site_info = " in the local site (" + local_site + ")"

    print "This script prints the status of the data store clusters{}.\n".format(local_site_info)

    plugin_dir = '/usr/share/clearwater/clearwater-cluster-manager/plugins'
    if os.path.isdir(plugin_dir):
        plugins = [(plugin_name[:-10]).capitalize() for plugin_name in os.listdir(plugin_dir) if
                plugin_name.endswith('_plugin.py')]

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

    start_with_store = {}               # organize cluster key by store type
    for (key, value) in cluster_values.items():
        # Check if the key relates to clustering. The clustering key has the format
        # /clearwater*[</optional site name>]/<node type>/clustering/<store type>
        key_parts = key.split('/')

        if 'clustering' in key_parts:
            if len(key_parts) > 5:
                site = key_parts[2]
                store_name = key_parts[5]
            elif len(key_parts) > 4:
                site = ""
                store_name = key_parts[4]
            start_with_store["{}-{}".format(store_name, site)] = value
        else:
            # The key isn't to do with clustering, skip it
            continue

    unstable_clusters = 0
    for (key, value) in sorted(start_with_store.items()):
        key_parts = key.split('-')
        store_name = key_parts[0]
        cluster_value = ""

        if len(key_parts) == 2 and sites != "":
            site = key_parts[1]
            cluster_value += "Describing the {} cluster in site {}:\n".format(store_name.capitalize(), site)
        else:
            cluster_value += "Describing the {} cluster:\n".format(store_name.capitalize())

        cluster = json.loads(value)
        cluster_ok = all([state == "normal"
                          for node, state in cluster.iteritems()])

        if cluster_ok:
            cluster_value += "  The cluster is stable.\n"
        else:
            cluster_value += "  The cluster is *not* stable.\n"
            unstable_clusters += 1

        if len(cluster) != 0:
            for node, state in cluster.iteritems():
                cluster_value += "    {} is in state {}.\n".format(node, state)

            print cluster_value

    # This makes sure an error value is returned when the clusters are not
    # stable
    return unstable_clusters

return_code = describe_clusters()
if return_code == 0:
    sys.exit()
else:
    clusters_state = "{} unstable cluster(s)".format(return_code)
    sys.exit(clusters_state)
