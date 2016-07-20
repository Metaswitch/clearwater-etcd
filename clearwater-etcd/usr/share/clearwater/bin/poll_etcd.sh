#!/bin/bash

# @file poll_etcd.sh
#
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

# This script polls the local etcd process. It checks whether etcd is healthy by
# trying to read local etcd stats. We need to do this rather than
# just use poll-tcp on port 4000 as etcd can listen to its port but still
# not be functioning correctly
. /etc/clearwater/config

[ $# -le 1 ] || { echo "Usage: poll_etcd [--quorum] (defaults to a local read)" >&2 ; exit 2 ; }

if [ -n "$1" ] && [ $1 == "--quorum" ]; then
  key_path="http://${management_local_ip:-$local_ip}:4000/v2/keys"
  key="/clearwater/${management_local_ip:-$local_ip}/liveness-check"
  path="$key_path$key -XPUT -d value=True"
  output="\"key\":\"$key\",\"value\":\"True\""
else
  path="http://${management_local_ip:-$local_ip}:4000/v2/stats/self"
  if [ ! -z "$etcd_cluster" ]; then
    # Configured as a master, so we will be in the list of etcd nodes.
    output="\"name\":\"${management_local_ip:-$local_ip}\""
  else
    # Configured as a proxy, so we won't be in the list of etcd nodes.
    # Just check that there is a configured master - we don't really
    # care about what it's name or address is.
    output="\"name\":\""
  fi
fi

curl -L $path 2> /tmp/poll-etcd.sh.stderr.$$ | tee /tmp/poll-etcd.sh.stdout.$$ | grep -q $output
rc=$?

# Check the return code and log if appropriate.
if [ $rc != 0 ] ; then
  echo etcd poll failed to $path    >&2
  cat /tmp/poll-etcd.sh.stderr.$$   >&2
  cat /tmp/poll-etcd.sh.stdout.$$   >&2
fi
rm -f /tmp/poll-etcd.sh.stderr.$$ /tmp/poll-etcd.sh.stdout.$$

exit $rc
