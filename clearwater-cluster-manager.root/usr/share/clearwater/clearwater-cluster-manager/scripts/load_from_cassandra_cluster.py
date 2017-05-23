# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import os
import subprocess
import sys
import etcd
import yaml
import json

local_ip = sys.argv[1]
node_type = sys.argv[2]
etcd_key = sys.argv[3]

assert os.path.exists("/etc/init.d/cassandra"), \
    "This script should be run on a node that's running Cassandra"

etcd_key = "/{}/{}/clustering/cassandra".format(etcd_key, node_type)

try:
    # Use nodetool describecluster to find the nodes in the existing cluster.
    # This returns a yaml document, but in order for pyyaml to recognise the
    # output as valid yaml, we need to use tr to replace tabs with spaces.
    # We remove any xss=.., as this can be printed out by 
    # cassandra-env.sh
    command = "/usr/share/clearwater/bin/run-in-signaling-namespace nodetool describecluster | grep -v \"^xss = \" | tr \"\t\" \" \""
    desc_cluster_output = subprocess.check_output(command, shell=True)
    doc = yaml.load(desc_cluster_output)
    servers = doc["Cluster Information"]["Schema versions"].values()[0]
    data = json.dumps({server: "normal" for server in servers})

    print "Inserting data %s into etcd key %s" % (data, etcd_key)

    c = etcd.Client(local_ip, 4000)
    new = c.write(etcd_key, data).value

    if new == data:
        print "Update succeeded"
    else:
        print "Update failed"
except subprocess.CalledProcessError as e:
    print ("'nodetool describecluster' failed"
           " with return code '%d' and output '%s'" % (e.returncode, e.output))
