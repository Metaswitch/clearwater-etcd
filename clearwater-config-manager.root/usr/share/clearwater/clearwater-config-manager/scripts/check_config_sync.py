#!/usr/share/clearwater/clearwater-config-manager/env/bin/python

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

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
