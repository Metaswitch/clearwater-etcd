# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import etcd
import sys

mgmt_node = sys.argv[1]
local_site = sys.argv[2]
queue_key = sys.argv[3]

client = etcd.Client(mgmt_node, 4000)
key = "/clearwater/{}/configuration/{}".format(local_site, queue_key)
default_value = "{\"ERRORED\": [], \"FORCE\": false, \"COMPLETED\": [], \"QUEUED\": []}"

c = etcd.Client(mgmt_node, 4000)
old = c.get(key).value

print "Replacing old data %s with new data %s" % (old, default_value)

new = c.write(key, default_value).value

if new == default_value:
    print "Update succeeded"
else:
    print "Update failed"
