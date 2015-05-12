import sys
import etcd
import json

local_ip = sys.argv[1]
local_site = sys.argv[2]
remote_site = sys.argv[3]
node_type = sys.argv[4]

assert node_type in ["sprout", "ralf", "memento"], \
    "Node type must be 'sprout', 'ralf' or 'memento'"

local_etcd_key = "/clearwater/{}/{}/clustering/memcached".format(local_site,
                                                                 node_type)
remote_etcd_key = "/clearwater/{}/{}/clustering/memcached".format(remote_site,
                                                                  node_type)

def strip_port(server):
    return server.rsplit(":", 1)[0].strip()

c = etcd.Client(local_ip, 4000)


def load_file_into_etcd(filename, etcd_key):
    with open(filename) as f:
        for line in f.readlines():
            key, value = line.split("=")
            assert key != "new_servers", \
                "Must not have a new_servers line when running this script"
            if key == "servers":
                data = json.dumps({strip_port(server): "normal"
                                for server in value.split(",")})

    print "Inserting data %s into etcd key %s" % (data, etcd_key)

    new = c.write(etcd_key, data).value

    if new == data:
        print "Update succeeded"
    else:
        print "Update failed"

load_file_into_etcd('/etc/clearwater/cluster_settings', local_etcd_key)

if remote_site != "":
    load_file_into_etcd('/etc/clearwater/remote_cluster_settings', remote_etcd_key)
