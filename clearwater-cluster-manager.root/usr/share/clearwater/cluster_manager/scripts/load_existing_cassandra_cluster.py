import subprocess
import sys
import etcd
import yaml
import json

local_ip = sys.argv[1]
node_type = sys.argv[2]

assert node_type in ["homestead", "homer", "memento"], \
    "Node type must be 'homestead', 'homer' or 'memento'"

etcd_key = "/{}/clustering/cassandra".format(node_type)

try:
    desc_cluster_output = subprocess.check_output(
        "nodetool describecluster | tr \"\t\" \" \"", shell=True)
    doc = yaml.load(desc_cluster_output)
    servers = doc["Cluster Information"]["Schema versions"].values()[0]
    data = json.dumps({server: "normal" for server in servers})
except subprocess.CalledProcessError as e:
    print ("'nodetool describecluster' failed"
           " with return code '%d' and output '%s'" % (e.returncode, e.output))

print "Inserting data %s into etcd key %s" % (data, etcd_key)

c = etcd.Client(local_ip, 4000)
new = c.write(etcd_key, data).value

if new == data:
    print "Update succeeded"
else:
    print "Update failed"
