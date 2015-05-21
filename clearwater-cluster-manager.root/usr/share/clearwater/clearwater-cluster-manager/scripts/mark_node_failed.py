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

print "Detailed output being sent to mark_node_failed.log"
logging.basicConfig(filename="mark_node_failed.log",
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)

local_ip = sys.argv[1]
site = sys.argv[2]
node_type = sys.argv[3]
datastore = sys.argv[4]
dead_node_ip = sys.argv[5]

key = make_key(site, node_type, datastore)
logging.info("Using etcd key %s" % (key))

error_syncer = EtcdSynchronizer(NullPlugin(key), dead_node_ip, etcd_ip=local_ip, force_leave=True)

print "Marking node as failed to allow current operation to complete..."
# Move the dead node into ERROR state to allow in-progress operations to
# complete
error_syncer.mark_node_failed()

# Move the dead node out of the cluster
error_syncer.start_thread()
print "Beginning process of leaving the cluster - will take at least 30 seconds"
error_syncer.leave_cluster()

# Wait for it to leave
error_syncer.thread.join()
print "Process complete - %s has left the cluster" % dead_node_ip

c = etcd.Client(local_ip, 4000)
new_state = c.get(key).value

print "New etcd state (after removing %s) is %s" % (dead_node_ip, new_state)
