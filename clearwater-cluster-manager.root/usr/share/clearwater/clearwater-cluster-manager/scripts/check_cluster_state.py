# Project Clearwater - IMS in the Cloud
# Copyright (C) 2015  Metaswitch Networks Ltd
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


import sys
import etcd
import json

mgmt_node = sys.argv[1]
local_node = sys.argv[2]
local_site = sys.argv[3]
remote_site = sys.argv[4]

datastores = [
    ("sprout", "memcached", local_site),
    ("sprout", "memcached", remote_site),
    ("sprout", "chronos", local_site),
    ("sprout", "chronos", remote_site),
    ("ralf", "memcached", local_site),
    ("ralf", "memcached", remote_site),
    ("ralf", "chronos", local_site),
    ("ralf", "chronos", remote_site),
    ("homestead", "cassandra", ""),
    ("homer", "cassandra", ""),
    ("memento", "memcached", local_site),
    ("memento", "memcached", remote_site),
    ("memento", "cassandra", "")
]

client = etcd.Client(mgmt_node, 4000)


def describe_cluster(node_type, site, store_name):
    key = "/clearwater/{}/{}/clustering/{}".format(site, node_type, store_name)

    try:
        result = client.get(key)
    except etcd.EtcdKeyNotFound:
        # There's none of the particular node type in the deployment
        return

    if result.value == "":
        # Cluster does not exist
        return

    if site != "":
        print "Describing the {} {} cluster in site {}:".format(node_type.capitalize(), store_name.capitalize(), site)
    else:
        print "Describing the {} {} cluster:".format(node_type.capitalize(), store_name.capitalize())

    cluster = json.loads(result.value)
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

for node_type, store_name, site in datastores:
    describe_cluster(node_type, site, store_name)
