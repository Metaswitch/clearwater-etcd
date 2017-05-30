# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import json
import subprocess
import sys

filename = sys.argv[1]

print("Loading etcd cluster info from {0}\n".format(filename))

data = {}

# Load saved data from the temp file
with open(filename, "r") as loaded_file:
    data = json.load(loaded_file)

# Add to etcd
for key, value in data.iteritems():
    subprocess.check_output(["clearwater-etcdctl", "set", key, value])

print("Loaded etcd cluster info from disk")

