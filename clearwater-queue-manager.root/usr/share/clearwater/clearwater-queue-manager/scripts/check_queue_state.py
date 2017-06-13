# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

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
    
    print "\n"
describe_queue_state()
