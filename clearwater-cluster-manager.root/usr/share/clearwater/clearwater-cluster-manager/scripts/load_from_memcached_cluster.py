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

import sys
import etcd
import json
import os

local_ip = sys.argv[1]
local_site = sys.argv[2]
remote_site = sys.argv[3]
node_type = sys.argv[4]

assert os.path.exists("/etc/init.d/clearwater-memcached"), \
    "This script should be run on a node that's running Memcached"

local_etcd_key = "/clearwater/{}/{}/clustering/memcached".format(local_site,
                                                                 node_type)
remote_etcd_key = "/clearwater/{}/{}/clustering/memcached".format(remote_site,
                                                                  node_type)

def strip_port(server):
    return server.rsplit(":", 1)[0].strip()

c = etcd.Client(local_ip, 4000)


def load_file_into_etcd(filename, etcd_key):
    with open(filename) as f:
        for line in f.readlines():
            if '=' in line:
                key, value = line.split("=")
                assert key != "new_servers", \
                    "Must not have a new_servers line when running this script"
                if key == "servers":
                    data = json.dumps({strip_port(server): "normal"
                                    for server in value.split(",")})

    print "Inserting data %s into etcd key %s" % (data, etcd_key)

    new = c.write(etcd_key, data).value

    if new == data:
        print "Update succeeded"
    else:
        print "Update failed"

if node_type == 'memento' and os.path.isfile('/etc/clearwater/memento_cluster_settings'):
    load_file_into_etcd('/etc/clearwater/memento_cluster_settings', local_etcd_key)
else:
    load_file_into_etcd('/etc/clearwater/cluster_settings', local_etcd_key)

if remote_site != "":
    load_file_into_etcd('/etc/clearwater/remote_cluster_settings', remote_etcd_key)
