# Copyright (C) Metaswitch Networks 2015
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import os
from os import sys
import etcd
import logging
from metaswitch.clearwater.cluster_manager.etcd_synchronizer import \
    EtcdSynchronizer
from metaswitch.clearwater.cluster_manager.null_plugin import \
    NullPlugin
from metaswitch.clearwater.etcd_shared.plugin_utils import run_command

def make_key(site, node_type, datatore, etcd_key):
    if datastore == "cassandra":
        return "/{}/{}/clustering/{}".format(etcd_key, node_type, datastore)
    else:
        return "/{}/{}/{}/clustering/{}".format(etcd_key, site, node_type, datastore)

logfile = "/var/log/clearwater-etcd/mark_node_failed.log"
print "Detailed output being sent to %s" % logfile
logging.basicConfig(filename=logfile,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)

local_ip = sys.argv[1]
site = sys.argv[2]
node_type = sys.argv[3]
datastore = sys.argv[4]
dead_node_ip = sys.argv[5]
etcd_key = sys.argv[6]

key = make_key(site, node_type, datastore, etcd_key)
logging.info("Using etcd key %s" % (key))

if datastore == "cassandra":
  try:
    sys.path.append("/usr/share/clearwater/clearwater-cluster-manager/failed_plugins")
    from cassandra_failed_plugin import CassandraFailedPlugin
    error_syncer = EtcdSynchronizer(CassandraFailedPlugin(key, dead_node_ip), dead_node_ip, etcd_ip=local_ip, force_leave=True)
  except ImportError:
    print "You must run mark_node_failed on a node that has Cassandra installed to remove a node from a Cassandra cluster"
    sys.exit(1)
else:
  error_syncer = EtcdSynchronizer(NullPlugin(key), dead_node_ip, etcd_ip=local_ip, force_leave=True)

print "Marking node as failed and removing it from the cluster - will take at least 30 seconds"
# Move the dead node into ERROR state to allow in-progress operations to
# complete
error_syncer.mark_node_failed()

# Move the dead node out of the cluster
error_syncer.start_thread()
error_syncer.leave_cluster()

# Wait for it to leave
error_syncer.thread.join()

print "Process complete - %s has left the cluster" % dead_node_ip

c = etcd.Client(local_ip, 4000)
new_state = c.get(key).value

logging.info("New etcd state (after removing %s) is %s" % (dead_node_ip, new_state))
