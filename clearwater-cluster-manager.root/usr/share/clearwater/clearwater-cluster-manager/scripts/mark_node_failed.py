import sys
from metaswitch.clearwater.cluster_manager.etcd_synchronizer import \
    EtcdSynchronizer
import etcd

local_ip = sys.argv[1]
key = sys.argv[2]
dead_node_ip = sys.argv[3]
error_syncer = EtcdSynchronizer(NullPlugin(None), '10.0.0.2')
error_syncer.mark_node_failed()

c = etcd.Client(local_ip, 4000)
new_state = c.get(key).value

print "New etcd state (after removing %s) is %s" % (dead_node_ip, new_state)
