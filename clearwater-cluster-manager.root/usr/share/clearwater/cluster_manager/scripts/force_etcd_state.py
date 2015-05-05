import sys
import etcd

local_ip = sys.argv[1]
key = sys.argv[2]
json_file = sys.argv[3]
data = ""
with open(json_file) as f:
    data = f.read()

c = etcd.Client(local_ip, 4001)
old =  c.get(key).value

print "Replacing old data %s with new data %s" % (old, data)

new = c.write(key, data).value

if new == data:
    print "Update succeeded"
else:
    print "Update failed"
