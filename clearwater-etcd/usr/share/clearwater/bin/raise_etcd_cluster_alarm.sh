#!/bin/bash

# @file raise_etcd_cluster_alarm.sh
#
# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

ALARM_TO_RAISE_FILE="/tmp/.clearwater_etcd_alarm_to_raise"

# Read in the alarm from the ALARM_TO_RAISE_FILE and raise it.
if [ -f $ALARM_TO_RAISE_FILE ] ; then
    alarm=`cat $ALARM_TO_RAISE_FILE`
    /usr/share/clearwater/bin/issue-alarm "monit" $alarm
fi


