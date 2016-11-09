# Project Clearwater - IMS in the Cloud
# Copyright (C) 2016 Metaswitch Networks Ltd
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

