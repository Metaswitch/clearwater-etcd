# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


# Cluster states
EMPTY = "empty"
STABLE = "stable"
STABLE_WITH_ERRORS = "stable with errors"
JOIN_PENDING = "join pending"
STARTED_JOINING = "started joining"
JOINING_CONFIG_CHANGING = "joining, config changing"
JOINING_RESYNCING = "joining, resyncing"
LEAVE_PENDING = "leave pending"
STARTED_LEAVING = "started leaving"
LEAVING_CONFIG_CHANGING = "leaving, config changing"
LEAVING_RESYNCING = "leaving, resyncing"
FINISHED_LEAVING = "finished leaving"
INVALID_CLUSTER_STATE = "invalid cluster state"

# Node states
WAITING_TO_JOIN = "waiting to join"
JOINING = "joining"
JOINING_ACKNOWLEDGED_CHANGE = "joining, acknowledged change"
JOINING_CONFIG_CHANGED = "joining, config changed"
NORMAL = "normal"
NORMAL_ACKNOWLEDGED_CHANGE = "normal, acknowledged change"
NORMAL_CONFIG_CHANGED = "normal, config changed"
WAITING_TO_LEAVE = "waiting to leave"
LEAVING = "leaving"
LEAVING_ACKNOWLEDGED_CHANGE = "leaving, acknowledged change"
LEAVING_CONFIG_CHANGED = "leaving, config changed"
FINISHED = "finished"
ERROR = "error"

# Pseudo-state - this state never gets written into etcd, we just delete the
# node's entry from etcd when we hit this state
DELETE_ME = "DELETE_ME"
