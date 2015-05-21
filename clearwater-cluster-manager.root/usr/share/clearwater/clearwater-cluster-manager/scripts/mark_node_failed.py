import sys
from metaswitch.clearwater.cluster_manager.etcd_synchronizer import \
    EtcdSynchronizer
from metaswitch.clearwater.cluster_manager.null_plugin import \
    NullPlugin
import etcd
import logging

def make_key(site, node_type, datatore):
    if datastore == "cassandra":
        return "/clearwater/{}/clustering/{}".format(node_type, datastore)
    else:
        return "/clearwater/{}/{}/clustering/{}".format(site, node_type, datastore)

root_log = logging.getLogger()
root_log.setLevel(logging.INFO)

local_ip = sys.argv[1]
site = sys.argv[2]
node_type = sys.argv[3]
datastore = sys.argv[4]
dead_node_ip = sys.argv[5]

key = make_key(site, node_type, datastore)
print "Using etcd key %s" % (key)

error_syncer = EtcdSynchronizer(NullPlugin(key), local_ip, etcd_ip=dead_node_ip, force_leave=True)
error_syncer.mark_node_failed()

c = etcd.Client(local_ip, 4000)
new_state = c.get(key).value

print "New etcd state (after removing %s) is %s" % (dead_node_ip, new_state)
