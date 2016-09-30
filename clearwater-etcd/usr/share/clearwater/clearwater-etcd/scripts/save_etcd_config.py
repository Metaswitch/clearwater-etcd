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

import datetime
import json
import re
import subprocess
import sys


# Gets the value from etcd for the given key
def get_value(key):
    stored_value = subprocess.check_output(["clearwater-etcdctl", "get", key])
    return stored_value.strip()


# Save the config
def save_to_disk(data, filename):
    with open(filename, "w+") as saved_config_file:
        json.dump(data, saved_config_file)


# Produces a dictionary like {"[node_ip]": "normal"} containing every cassandra
# node in the local site
def get_local_cassandra_nodes(site_name):
    nodetool_process = subprocess.Popen("/usr/share/clearwater/bin/run-in-signaling-namespace nodetool status",
                                        stdout=subprocess.PIPE,
                                        shell=True)
    nodes = {}

    # regex which matches from the beginning of the string, expecting U or D,
    # then N, L, J or M, then captures the next word (between whitespace)
    # This is the IP address of the node, e.g.:
    #
    # UN  10.0.144.102  79.67 KB   256     100.0%            090e6728-d592-4c75-b38d-7c25683bc133  RAC1
    regex = "[U|D][N|L|J|M]\s*([^\s]+)"

    found_local_section = False

    for line in nodetool_process.stdout:
        # Remove trailing whitespace
        line = line.strip()

        if not found_local_section:
            # Loop through until we find the Datacenter: [local_site_name] line
            # indicating that the following nodes are part of the local site
            if "Datacenter: {0}".format(site_name) in line:
                found_local_section = True
        else:
            # Now, loop until we hit the next Datacenter line, looking for nodes
            if "Datacenter: " in line:
                break

            m = re.match(regex, line)
            if m:
                nodes[m.group(1)] = "normal"

    return nodes


# Start

local_site_name = sys.argv[1]

# Allow the user to specify the save location
save_dir = raw_input("Enter the directory to save the config. Leave blank for default (/home/clearwater/ftp/) ")

if save_dir == "":
    save_dir = "/home/clearwater/ftp/"

if not save_dir.endswith("/"):
    save_dir = save_dir + "/"

filename = save_dir + "saved-etcd-config-" + datetime.datetime.now().strftime('%y-%m-%d')

print("Saving etcd cluster info to {0}\n".format(filename))

try:
    # List all keys stored in etcd
    # -p appends a "/" to all directories to help distinguish them from keys
    output_str = subprocess.check_output(["clearwater-etcdctl", "ls", "-p", "--recursive"])

    # Dictionary that will contain all the key-value pairs that we want to save
    data_to_save = {}

    # First, save all keys that contain the local site name
    for line in output_str.splitlines():
        line = line.strip()

        # Save any keys that contain the local site name
        if (not line.endswith("/")) and ("/{0}/".format(local_site_name) in line):
            value = get_value(line)
            data_to_save[line] = value

    # Now we need to add the homestead cassandra clustering info, but we only
    # want to add the nodes for the local site, so we build this manually
    nodes = get_local_cassandra_nodes(local_site_name)
    data_to_save["/clearwater/vellum/clustering/cassandra"] = json.dumps(nodes)

    # Now save the dictionary of keys we want to preserve
    save_to_disk(data_to_save, filename)

    print("Saved etcd cluster info to disk")

except subprocess.CalledProcessError, e:
    print("ERROR: Unable to contact etcd.")
    print("ERROR: Confirm etcd is running and try again.")

