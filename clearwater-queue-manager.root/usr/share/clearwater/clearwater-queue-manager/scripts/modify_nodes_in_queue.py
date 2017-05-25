# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

from os import sys
import etcd
import logging
from metaswitch.clearwater.queue_manager.etcd_synchronizer import EtcdSynchronizer, WriteToEtcdStatus
from metaswitch.clearwater.queue_manager.null_plugin import NullPlugin
from time import sleep

def make_key(site, clearwater_key, queue_key):
    return "/{}/{}/configuration/{}".format(clearwater_key, site, queue_key)

logfile = "/var/log/clearwater-queue-manager/queue_operation.log"
logging.basicConfig(filename=logfile,
                    format="%(asctime)s.%(msecs)03d UTC %(levelname)s %(filename)s:%(lineno)d: %(message)s",
                    datefmt="%d-%m-%Y %H:%M:%S",
                    level=logging.DEBUG)

operation = sys.argv[1]
local_ip = sys.argv[2]
site = sys.argv[3]
node_type = sys.argv[4]
clearwater_key = sys.argv[5]
queue_key = sys.argv[6]

logging.info("Using etcd key %s" % queue_key)

queue_syncer = EtcdSynchronizer(NullPlugin(queue_key), local_ip, site, clearwater_key, node_type)

if operation == "add":
    logging.debug("Adding %s to queue to restart" % (local_ip + "-" + node_type))

    while queue_syncer.add_to_queue() != WriteToEtcdStatus.SUCCESS:
        sleep(2)

    logging.debug("Node successfully added to restart queue")
elif operation == "remove_success":
    logging.debug("Removing %s from front of queue" % (local_ip + "-" + node_type))

    while queue_syncer.remove_from_queue(True) != WriteToEtcdStatus.SUCCESS:
        sleep(2)

    logging.debug("Node successfully removed")
elif operation == "remove_failure":
    logging.debug("Removing %s from front of queue and marking as errored" % (local_ip + "-" + node_type))

    while queue_syncer.remove_from_queue(False) != WriteToEtcdStatus.SUCCESS:
        sleep(2)

    logging.debug("Node successfully removed")
elif operation == "force_true":
    logging.debug("Setting the force value to true")

    while queue_syncer.set_force(True) != WriteToEtcdStatus.SUCCESS:
        sleep(2)

    logging.debug("Force value successfully set")
elif operation == "force_false":
    logging.debug("Setting the force value to false")

    while queue_syncer.set_force(False) != WriteToEtcdStatus.SUCCESS:
        sleep(2)

    logging.debug("Force value successfully set")
else:
    logging.debug("Invalid operation requested")

c = etcd.Client(local_ip, 4000)
key = make_key(site, clearwater_key, queue_key)
queue = c.get(key).value
logging.info("New etcd state is %s" % (queue))
