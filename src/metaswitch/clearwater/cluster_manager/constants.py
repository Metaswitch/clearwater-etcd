# Cluster states
STABLE = "stable"
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

# Alarm entries
RAISE_TOO_LONG_CLUSTERING = "5600.4"
CLEAR_TOO_LONG_CLUSTERING = "5600.1"

RAISE_MEMCACHED_NOT_YET_CLUSTERED = "3500.4"
CLEAR_MEMCACHED_NOT_YET_CLUSTERED = "3500.1"

RAISE_CASSANDRA_NOT_YET_CLUSTERED = "4002.4"
CLEAR_CASSANDRA_NOT_YET_CLUSTERED = "4002.1"
CLEAR_CASSANDRA_NOT_YET_DECOMMISSIONED = "4003.4"
CLEAR_CASSANDRA_NOT_YET_DECOMMISSIONED = "4003.1"
