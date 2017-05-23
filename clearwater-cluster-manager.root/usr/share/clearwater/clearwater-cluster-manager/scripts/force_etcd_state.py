# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import sys
import etcd

local_ip = sys.argv[1]
key = sys.argv[2]
json_file = sys.argv[3]
data = ""
with open(json_file) as f:
    data = f.read()

c = etcd.Client(local_ip, 4000)
old =  c.get(key).value

print "Replacing old data %s with new data %s" % (old, data)

new = c.write(key, data).value

if new == data:
    print "Update succeeded"
else:
    print "Update failed"
