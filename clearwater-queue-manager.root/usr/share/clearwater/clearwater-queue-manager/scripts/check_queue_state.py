# Project Clearwater - IMS in the Cloud
# Copyright (C) 2016  Metaswitch Networks Ltd
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
local_site = sys.argv[2]
queue_key = sys.argv[3]

client = etcd.Client(mgmt_node, 4000)

def describe_queue_state():
    print "Describing the current queue state for {}".format(queue_key)

    # Pull out all the clearwater keys.
    key = "/clearwater/{}/configuration/{}".format(local_site, queue_key)

    try:
        result = client.get(key)
    except etcd.EtcdKeyNotFound:
        # There's no clearwater keys yet
        print "  No queue exists for {}".format(queue_key)
        return

    values = json.loads(result.value)

    if values["QUEUED"]:
        print "  Nodes currently queued:"
        for node in values["QUEUED"]:
            print "    Node ID: {}, Node status: {}".format(node["ID"], node["STATUS"].lower())
    else:
        print "  No nodes are currently queued"

    if values["ERRORED"]:
        print "  Nodes in an errored state:"
        for node in values["ERRORED"]:
            print "    Node ID: {}, Node status: {}".format(node["ID"], node["STATUS"].lower())


    if values["COMPLETED"]:
        print "  Nodes that have completed:"
        for node in values["COMPLETED"]:
            print "    Node ID: {}".format(node["ID"])

describe_queue_state()
