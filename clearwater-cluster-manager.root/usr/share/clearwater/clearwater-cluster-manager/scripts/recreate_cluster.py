# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import json
import subprocess
import sys


# Gets the value from etcd for the given key
def get_value(key):
    stored_value = subprocess.check_output(["clearwater-etcdctl", "get", key])
    return stored_value.strip()


# Start

old_node_type = sys.argv[1]
new_node_type = sys.argv[2]
storage_type = sys.argv[3]

print("Copying cluster information for {0} on {1} to {2}".format(storage_type,
                                                                 old_node_type,
                                                                 new_node_type))

try:
    # List all keys stored in etcd
    # -p appends a "/" to all directories to help distinguish them from keys
    output_str = subprocess.check_output(["clearwater-etcdctl", "ls", "-p", "--recursive"])
    new_data = {}

    for line in output_str.splitlines():
        line = line.strip()

        # Only need to rename keys containing the old node name for this storage type
        if (line.endswith("/{0}".format(storage_type))) and ("/{0}/".format(old_node_type) in line):
            value = get_value(line)
            new_key = line.replace("/{0}/".format(old_node_type), "/{0}/".format(new_node_type))
            new_data[new_key] = value

    # Add the new key-value pairs
    for key, value in new_data.iteritems():
        subprocess.check_output(["clearwater-etcdctl", "set", key, value])

    print("Done")

except subprocess.CalledProcessError, e:
    print("ERROR: Unable to contact etcd.")
    print("ERROR: Confirm etcd is running and try again.")

