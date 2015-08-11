# Project Clearwater - IMS in the Cloud
# Copyright (C) 2015 Metaswitch Networks Ltd
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version, along with the "Special Exception" for use of
# the program along with SSL, set forth below. This program is distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details. You should have received a copy of the GNU General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
# The author can be reached by email at clearwater@metaswitch.com or by
# post at Metaswitch Networks Ltd, 100 Church St, Enfield EN2 6BQ, UK
#
# Special Exception
# Metaswitch Networks Ltd  grants you permission to copy, modify,
# propagate, and distribute a work formed by combining OpenSSL with The
# Software, or a work derivative of such a combination, even if such
# copying, modification, propagation, or distribution would otherwise
# violate the terms of the GPL. You must comply with the GPL in all
# respects for all of the code used other than OpenSSL.
# "OpenSSL" means OpenSSL toolkit software distributed by the OpenSSL
# Project and licensed under the OpenSSL Licenses, or a work based on such
# software and licensed under the OpenSSL Licenses.
# "OpenSSL Licenses" means the OpenSSL License and Original SSLeay License
# under which the OpenSSL Project distributes the OpenSSL toolkit software,
# as those licenses appear in the file LICENSE-OPENSSL.

import os
import subprocess
import sys
import etcd
import yaml
import json

local_ip = sys.argv[1]
node_type = sys.argv[2]
sig_namespace = sys.argv[3]

assert os.path.exists("/etc/init.d/cassandra"), \
    "This script should be run on a node that's running Cassandra"

etcd_key = "/clearwater/{}/clustering/cassandra".format(node_type)

try:
    # Use nodetool describecluster to find the nodes in the existing cluster.
    # This returns a yaml document, but in order for pyyaml to recognise the
    # output as valid yaml, we need to use tr to replace tabs with spaces.
    # We remove any xss=.., as this can be printed out by 
    # cassandra-env.sh
    command = "nodetool describecluster | grep -v \"^xss = \" | tr \"\t\" \" \""
    if sig_namespace:
        command = "ip netns exec {} ".format(sig_namespace) + command

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
