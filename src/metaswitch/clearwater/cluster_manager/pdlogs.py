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

from metaswitch.common.pdlogs import PDLog

STARTUP = PDLog(
    number=PDLog.CL_CLUSTER_MGR_ID+1,
    desc="clearwater-cluster-manager has started.",
    cause="The application is starting.",
    effect="Normal.",
    action="None.",
    priority=PDLog.LOG_NOTICE)
EXITING = PDLog(
    number=PDLog.CL_CLUSTER_MGR_ID+2,
    desc="clearwater-cluster-manager is exiting.",
    cause="The application is exiting.",
    effect="Datastore cluster management services are no longer available.",
    action="This occurs normally when the application is stopped. Wait for monit "+\
      "to restart the application.",
    priority=PDLog.LOG_ERR)
EXITING_BAD_CONFIG = PDLog(
    number=PDLog.CL_CLUSTER_MGR_ID+3,
    desc="clearwater-cluster-manager is exiting due to bad configuration.",
    cause="clearwater-cluster-manager was started with incorrect configuration.",
    effect="Datastore cluster management services are no longer available.",
    action="Verify that the configuration files in /etc/clearwater/ are correct "+\
      "according to the documentation.",
    priority=PDLog.LOG_ERR)
NODE_JOINING = PDLog(
    number=PDLog.CL_CLUSTER_MGR_ID+4,
    desc="A node is joining a datastore cluster.",
    cause="Node {ip} has started to join the {cluster_desc}.",
    effect="Normal.",
    action="None.",
    priority=PDLog.LOG_NOTICE)
NODE_LEAVING = PDLog(
    number=PDLog.CL_CLUSTER_MGR_ID+5,
    desc="A node is leaving a datastore cluster.",
    cause="Node {ip} has started to leave the {cluster_desc}.",
    effect="Normal.",
    action="None.",
    priority=PDLog.LOG_NOTICE)
NOT_YET_CLUSTERED_ALARM = PDLog(
    number=PDLog.CL_CLUSTER_MGR_ID+6,
    desc="This node is not yet clustered.",
    cause="This node has not yet joined the {cluster_desc}.",
    effect="This node will alarm until the cluster is joined.",
    action="Wait for this node to join the cluster. If this does not happen, "+\
      "ensure that clearwater-etcd and clearwater-cluster-manager have started "+\
      "up, and fix any other errors relating to them.",
    priority=PDLog.LOG_ERR)
TOO_LONG_ALARM = PDLog(
    number=PDLog.CL_CLUSTER_MGR_ID+7,
    desc="A scaling operation has taken too long.",
    cause="A scaling operation for the {cluster_desc} has been in progress for more than 15 minutes.",
    effect="This node will alarm until the operation finishes. "+\
      "No further scaling operations can begin until this one completes.",
    action="Ensure that clearwater-etcd is running, and fix any errors relating "+\
      "to it. If any nodes are temporarily failed, recover them. If any nodes "+\
      "are permanently failed, follow the documentation to remove them from the cluster.",
    priority=PDLog.LOG_ERR)
EXITING_MISSING_ETCD_CLUSTER_KEY = PDLog(
    number=PDLog.CL_CLUSTER_MGR_ID+8,
    desc="clearwater-cluster-manager is exiting due to missing configuration.",
    cause="clearwater-cluster-manager was started without the mandatory etcd_cluster_key parameter.",
    effect="Datastore cluster management services are no longer available.",
    action="Verify that the configuration file /etc/clearwater/local_config is correct "+\
      "according to the documentation.",
    priority=PDLog.LOG_ERR)
DO_NOT_CLUSTER = PDLog(
    number=PDLog.CL_CLUSTER_MGR_ID+9,
    desc="clearwater-cluster-manager isn't starting any plugins due to the configuration.",
    cause="clearwater-cluster-manager was started with the etcd_cluster_key set to DO_NOT_CLUSTER, "+\
      "so this node will not join any data store clusters.",
    effect="This node will not join data store clusters.",
    action="If this is unexpected, change the etcd_cluster_key in /etc/clearwater/local_config.",
    priority=PDLog.LOG_NOTICE)
DO_NOT_START = PDLog(
    number=PDLog.CL_CLUSTER_MGR_ID+10,
    desc="clearwater-cluster-manager isn't starting any plugins due to the configuration.",
    cause="clearwater-cluster-manager was started with the cluster_manager_enabled value not set to 'Y', "+\
      "so this node will not join any data store clusters.",
    effect="This node will not join data store clusters.",
    action="If this is unexpected, change the cluster_manager_enabled value in /etc/clearwater/shared_config.",
    priority=PDLog.LOG_NOTICE)
STABLE_CLUSTER = PDLog(
    number=PDLog.CL_CLUSTER_MGR_ID+11,
    desc="This node is part of a stable data store cluster.",
    cause="This node is a member of the {cluster_desc}.",
    effect="Normal.",
    action="None.",
    priority=PDLog.LOG_NOTICE)
