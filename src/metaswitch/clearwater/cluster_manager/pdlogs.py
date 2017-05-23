# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

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
