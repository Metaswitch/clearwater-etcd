#!/usr/share/clearwater/clearwater-config-manager/env/bin/python

# Project Clearwater - IMS in the Cloud
# Copyright (C) 2015  Metaswitch Networks Ltd
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

from metaswitch.clearwater.etcd_shared.plugin_loader import load_plugins_in_dir
from metaswitch.clearwater.config_manager.plugin_base import FileStatus
import etcd
import os
import sys

etcd_ip = sys.argv[1]
site = sys.argv[2]
etcd_key = sys.argv[3]

client = etcd.Client(etcd_ip, 4000)

plugins_dir = "/usr/share/clearwater/clearwater-config-manager/plugins/"
plugins = load_plugins_in_dir(plugins_dir)

rc = 0

for plugin in plugins:
    try:
        result = client.get("/" + etcd_key + "/" + site + "/configuration/" + plugin.key())
        value = result.value
    except etcd.EtcdKeyNotFound:
        value = ""

    state = plugin.status(value)

    if state == FileStatus.UP_TO_DATE:
        print " - {} is up to date".format(plugin.file())
    elif state == FileStatus.OUT_OF_SYNC:
        print " - {} is present but is out of sync".format(plugin.file())
        rc = 1
    else:
        print " - {} is missing".format(plugin.file())
        rc = 1

sys.exit(rc)
