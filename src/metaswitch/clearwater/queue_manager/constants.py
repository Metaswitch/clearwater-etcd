# Copyright (C) Metaswitch Networks 2015
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

# JSON values
JSON_QUEUED = "QUEUED"
JSON_ERRORED = "ERRORED"
JSON_COMPLETED = "COMPLETED"
JSON_FORCE = "FORCE"
JSON_ID = "ID"
JSON_STATUS = "STATUS"

# STATUS values
S_QUEUED = "QUEUED"
S_PROCESSING = "PROCESSING"
S_FAILURE = "FAILURE"
S_UNRESPONSIVE = "UNRESPONSIVE"
S_DONE = "DONE"

# GLOBAL states
GS_NO_SYNC = "NO_SYNC"
GS_NO_SYNC_ERROR = "NO_SYNC_ERROR"
GS_SYNC = "SYNC"
GS_SYNC_ERROR = "SYNC_ERROR"

# LOCAL states
LS_NO_QUEUE = "NO_QUEUE"
LS_NO_QUEUE_ERROR = "NO_QUEUE_ERROR"
LS_FIRST_IN_QUEUE = "FIRST_IN_QUEUE"
LS_PROCESSING = "PROCESSING"
LS_WAITING_ON_OTHER_NODE = "WAITING_ON_OTHER_NODE"
LS_WAITING_ON_OTHER_NODE_ERROR = "WAITING_ON_OTHER_NODE_ERROR"
