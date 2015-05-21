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

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root_log.addHandler(ch)

local_ip = sys.argv[1]
site = sys.argv[2]
node_type = sys.argv[3]
datastore = sys.argv[4]
dead_node_ip = sys.argv[5]

key = make_key(site, node_type, datastore)
print "Using etcd key %s" % (key)

error_syncer = EtcdSynchronizer(NullPlugin(key), dead_node_ip, etcd_ip=local_ip, force_leave=True)

# Move the dead node into ERROR state to allow in-progress operations to
# complete
error_syncer.mark_node_failed()

# Move the dead node out of the cluster
error_syncer.start_thread()
error_syncer.leave_cluster()

# Wait for it to leave
error_syncer.thread.join()

c = etcd.Client(local_ip, 4000)
new_state = c.get(key).value

print "New etcd state (after removing %s) is %s" % (dead_node_ip, new_state)
