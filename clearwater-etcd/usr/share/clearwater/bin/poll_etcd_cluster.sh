#!/bin/bash

# @file poll_etcd_cluster.sh
#
# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

# This script is used by Monit to check connectivity to remote etcd instances.
# If connectivity is lost to any instances in the cluster, an alarm id is
# written to the ALARM_TO_RAISE_FILE. When monit notices that the cluster is
# unhealthy for a period of time, it raises the appropriate alarm (major
# severity for a single instance, critical severity if enough instances are
# unreachable that quorum can't be formed). When connectivity is restored to all
# instances, the alarm is cleared.
#
# Execution of etcdctl is "niced" to minimize the impact of its use.

ALARM_TO_RAISE_FILE="/tmp/.clearwater_etcd_alarm_to_raise"

. /etc/clearwater/config

# Return state of the etcd cluster, 0 if all nodes are up, 1 if some nodes are
# down, 2 if quorum has failed.
cluster_state()
{
    # Run etcdctl to get the status of the cluster, if successful continue to
    # check output, otherwise return 0 (local etcd failure is not considered a
    # cluster error).
    local out=`nice -n 19 /usr/bin/clearwater-etcdctl cluster-health 2> /dev/null`
    if [ "$?" = 0 ] ; then
      local unhealthy_cluster_state_regex="cluster is unhealthy"
      if [[ $out =~ $unhealthy_cluster_state_regex ]]
      then
        printf "$(date)\n$out\n" >> "/var/log/clearwater-etcd/etcd_cluster_bad_polls.log"
        return 2
      fi

      local maybe_unhealthy_cluster_state_regex="cluster may be unhealthy"
      if [[ $out =~ $maybe_unhealthy_cluster_state_regex ]]
      then
        printf "$(date)\n$out\n" >> "/var/log/clearwater-etcd/etcd_cluster_bad_polls.log"
        return 2
      fi

      IFS=$'\n'
      # The output of cluster-health can report the following:
      #   Member is healthy
      #   Member is unhealthy
      #   Member is unreachable
      local healthy_node_regex="member [a-zA-Z0-9]* is healthy"
      local unhealthy_node_regex="member [a-zA-Z0-9]* is unhealthy"
      local unreachable_node_regex="member [a-zA-Z0-9]* is unreachable"
      for line in $out
      do
        if [[ $line =~ $unhealthy_node_regex ]] || [[ $line =~ $unreachable_node_regex ]]
        then
          unhealthy_members=true
        elif [[ $line =~ $healthy_node_regex ]]
        then
          parse_member_ip $line
        fi
      done
      # If there are any healthy members, add them to a state file, so we can
      # rejoin safely if we die.
      if [[ ! -z $HEALTHY_MEMBER_LIST ]]
      then
        echo "$HEALTHY_MEMBER_LIST" > "/var/lib/clearwater-etcd/healthy_etcd_members"
      fi

      if [ $unhealthy_members ]
      then
        printf "$(date)\n$out\n" >> "/var/log/clearwater-etcd/etcd_cluster_bad_polls.log"
        return 1
      fi
    fi
    return 0
}


parse_member_ip()
{
    # The output of cluter health looks like:
    # member <member_id> is healthy: got healthy result from http://<member_ip>:4000
    # We want to pull out the ip, to build an up to date etcd_cluster value
    # The steps are:
    #   select the ninth section: http://<member_ip>:4000
    #   strip the 'http://' from the front
    #   cut the ':4000' from the end
    member_ip=$( echo $1 | cut -d " " -f 9 | sed 's/http:\/\///' | cut -d : -f 1 )
    HEALTHY_MEMBER_LIST=$member_ip,$HEALTHY_MEMBER_LIST
}


cluster_state
state=$?

echo $state

# If the cluster is healthy, remove alarm file and clear alarm.
# If not, write the alarm to the ALARM_TO_RAISE_FILE so that monit can raise it.
if [ "$state" = 0 ] ; then
    rm -f $ALARM_TO_RAISE_FILE > /dev/null 2>&1
    /usr/share/clearwater/bin/issue-alarm "monit" "6501.1"
elif [ "$state" = 1 ] ; then
    echo "6501.4" > $ALARM_TO_RAISE_FILE
else
    echo "6501.3" > $ALARM_TO_RAISE_FILE
fi

exit $state

