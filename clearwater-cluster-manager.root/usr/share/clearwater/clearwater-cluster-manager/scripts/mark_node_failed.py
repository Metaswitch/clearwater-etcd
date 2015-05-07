import sys
from metaswitch.clearwater.cluster_manager.etcd_synchronizer import \
    EtcdSynchronizer
from metaswitch.clearwater.cluster_manager.null_plugin import \
    NullPlugin
import etcd
import logging


root_log = logging.getLogger()
root_log.setLevel(logging.INFO)

local_ip = sys.argv[1]
key = sys.argv[2]
dead_node_ip = sys.argv[3]
error_syncer = EtcdSynchronizer(NullPlugin(key), local_ip, etcd_ip=dead_node_ip, force_leave=True)
error_syncer.mark_node_failed()

c = etcd.Client(local_ip, 4000)
new_state = c.get(key).value

print "New etcd state (after removing %s) is %s" % (dead_node_ip, new_state)
