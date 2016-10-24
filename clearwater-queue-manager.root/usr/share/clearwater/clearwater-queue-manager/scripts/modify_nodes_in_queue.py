# Project Clearwater - IMS in the Cloud
# Copyright (C) 2015 Metaswitch Networks Ltd
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version, along with the "Special Exception" for use of
# the program along with SSL, set forth below. This program is distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details. You should have received a copy of the GNU General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
# The author can be reached by email at clearwater@metaswitch.com or by
# post at Metaswitch Networks Ltd, 100 Church St, Enfield EN2 6BQ, UK
#
# Special Exception
# Metaswitch Networks Ltd  grants you permission to copy, modify,
# propagate, and distribute a work formed by combining OpenSSL with The
# Software, or a work derivative of such a combination, even if such
# copying, modification, propagation, or distribution would otherwise
# violate the terms of the GPL. You must comply with the GPL in all
# respects for all of the code used other than OpenSSL.
# "OpenSSL" means OpenSSL toolkit software distributed by the OpenSSL
# Project and licensed under the OpenSSL Licenses, or a work based on such
# software and licensed under the OpenSSL Licenses.
# "OpenSSL Licenses" means the OpenSSL License and Original SSLeay License
# under which the OpenSSL Project distributes the OpenSSL toolkit software,
# as those licenses appear in the file LICENSE-OPENSSL.

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
