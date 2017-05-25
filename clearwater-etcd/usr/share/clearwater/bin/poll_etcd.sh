#!/bin/bash

# @file poll_etcd.sh
#
# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

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
