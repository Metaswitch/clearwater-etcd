import sys
import etcd
import json

local_ip = sys.argv[1]
node_type = sys.argv[2]

assert node_type in ["sprout", "ralf"], "Node type must be 'sprout' or 'ralf'"

etcd_key = "/{}/clustering/memcached".format(node_type)

def strip_port(server):
    return server.rsplit(":", 1)[0].strip()

with open('/etc/clearwater/cluster_settings') as f:
    for line in f.readlines():
        key, value = line.split("=")
        assert key != "new_servers", "Must not have a new_servers line when running this script"
        if key == "servers":
            data = json.dumps({strip_port(server): "normal" for server in value.split(",")})

print "Inserting data %s into etcd key %s" % (data, etcd_key)

c = etcd.Client(local_ip, 4001)
new = c.write(etcd_key, data).value

if new == data:
    print "Update succeeded"
else:
    print "Update failed"
