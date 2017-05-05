#!/bin/bash

# @file clearwater-etcd.init.d
#
# Project Clearwater - IMS in the Cloud
# Copyright (C) 2013  Metaswitch Networks Ltd
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

### BEGIN INIT INFO
# Provides:          clearwater-etcd
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Clearwater etcd package
# Description:       Etcd package for Clearwater nodes
### END INIT INFO

# Author: Graeme Robertson <graeme.robertson@metaswitch.com>
#
# Please remove the "Author" lines above and replace them
# with your own name if you copy and modify this script.

# Do NOT "set -e"

DESC="etcd"
NAME=clearwater-etcd
DATA_DIR=/var/lib/$NAME
JOINED_CLUSTER_SUCCESSFULLY=$DATA_DIR/clustered_successfully
HEALTHY_CLUSTER_VIEW=$DATA_DIR/healthy_etcd_members
PIDFILE=/var/run/$NAME/$NAME.pid
DAEMON=/usr/bin/etcd
DAEMONWRAPPER=/usr/bin/etcdwrapper
USER=$NAME

# Exit if the package is not installed
[ -x "$DAEMON" ] || exit 0

# Read configuration variable file if it is present
#[ -r /etc/default/$NAME ] && . /etc/default/$NAME

# Load the VERBOSE setting and other rcS variables
. /lib/init/vars.sh

# Define LSB log_* functions.
# Depend on lsb-base (>= 3.2-14) to ensure that this file is present
# and status_of_proc is working.
. /lib/lsb/init-functions

. /etc/clearwater/config

listen_ip=${management_local_ip:-$local_ip}
advertisement_ip=${management_local_ip:-$local_ip}

generate_initial_cluster()
{
        # We are provided with a comma or space separated list of IP
        # addresses. We need to produce a list of comma separated
        # entries, where each entry should look like <name>=<peer url>.
        # Replace commas with whitespace, then split on whitespace (to
        # cope with etcd_cluster values that have spaces)
        # We generate names by just replacing dots with dashes.
        ETCD_INITIAL_CLUSTER=
        for server in ${1//,/ }
        do
            server_name=${server%:*}
            server_name=${server_name//./-}
            ETCD_INITIAL_CLUSTER="${server_name}=http://$server:2380,$ETCD_INITIAL_CLUSTER"
        done
}

create_cluster()
{
        echo Creating new cluster...

        # Build the initial cluster view string based on the IP addresses in
        # $etcd_cluster.
        generate_initial_cluster $etcd_cluster

        CLUSTER_ARGS="--initial-cluster $ETCD_INITIAL_CLUSTER
                      --initial-cluster-state new"
}

join_cluster_as_proxy()
{
        echo Joining cluster as proxy...

        # We can either be supplied with a complete proxy setup string
        # in $etcd_proxy, or a list of IP addresses, like etcd_cluster
        # Disambiguate the two based on if it has an "=" sign it.
        if [[ $etcd_proxy == *"="* ]]; then
            ETCD_INITIAL_CLUSTER="${etcd_proxy}"
        else
            # Build the initial cluster view string based on the IP addresses in
            # $etcd_proxy.
            generate_initial_cluster $etcd_proxy
        fi

        CLUSTER_ARGS="--initial-cluster $ETCD_INITIAL_CLUSTER --proxy on"
}

setup_etcdctl_peers()
{
        # If we were in a working cluster before, we will have saved off an up to
        # date view of the cluster. We want to override etcd_cluster or
        # etcd_proxy with this, so that functions later in this script use the
        # correct cluster value.
        if [ -f $HEALTHY_CLUSTER_VIEW ]
        then
          # We want to stip anything up to and including the first = character
          # so we can select etcd_cluster or etcd_proxy appropriately
          healthy_cluster=$(sed -e 's/.*=//' < $HEALTHY_CLUSTER_VIEW)
          if [ -n "$etcd_cluster" ]
          then
            etcd_cluster=$healthy_cluster
          elif [ -n "$etcd_proxy" ]
          then
            etcd_proxy=$healthy_cluster
          fi
        fi

        # Build the client list based on $etcd_cluster. Each entry is simply
        # <IP>:<port>, using the client port. Replace commas with whitespace,
        # then split on whitespace (to cope with etcd_cluster values that have spaces)
        export ETCDCTL_PEERS=
        servers=""
        if [ -n "$etcd_cluster" ]
        then
          servers=$etcd_cluster
        elif [ -n "$etcd_proxy" ]
        then
          servers=$etcd_proxy
        fi

        for server in ${servers//,/ }
        do
            if [[ $server != $advertisement_ip ]]
            then
                ETCDCTL_PEERS="$server:4000,$ETCDCTL_PEERS"
            fi
        done
}


join_cluster()
{
        # Joining existing cluster
        echo Joining existing cluster...

        # If this fails, then hold off trying again for a time. This stops us
        # overwhelming the etcd elections on a large scale-up.
        sleep $[$RANDOM%30]

        # We need a temp file to deal with the environment variables.
        TEMP_FILE=$(mktemp)

        setup_etcdctl_peers

        # Check to make sure the cluster we want to join is healthy.
        # If it's not, don't even try joining (it won't work, and may
        # cause problems with the cluster)
        /usr/bin/etcdctl cluster-health 2>&1 | grep "cluster is healthy"
        if [ $? -ne 0 ]
         then
           echo "Not joining an unhealthy cluster"
           exit 2
        fi

        # Tell the cluster we're joining
        /usr/bin/etcdctl member add $ETCD_NAME http://$advertisement_ip:2380
        if [[ $? != 0 ]]
        then
          local_member_id=$(/usr/bin/etcdctl member list | grep -F -w "http://$advertisement_ip:2380" | grep -o -E "^[^:]*" | grep -o "^[^[]\+")
          /usr/bin/etcdctl member remove $local_member_id
          rm -rf $DATA_DIR/$advertisement_ip
          echo "Failed to add local node to cluster"
          exit 2
        fi

        ETCD_INITIAL_CLUSTER=$(/usr/share/clearwater/bin/get_etcd_initial_cluster.py $advertisement_ip $etcd_cluster)

        CLUSTER_ARGS="--initial-cluster $ETCD_INITIAL_CLUSTER
                      --initial-cluster-state existing"

        # daemon is not running, so attempt to start it.
        ulimit -Hn 10000
        ulimit -Sn 10000
        ulimit -c unlimited

        # Tidy up
        rm $TEMP_FILE
}

#
# Function to join/create an etcd cluster based on the `etcd_cluster` variable
#
# Sets the CLUSTER_ARGS variable to an appropriate value to use as arguments to
# etcd.
#
join_or_create_cluster()
{
        # We only want to create the cluster if we are both a founding member,
        # and we have never successfully clustered before. Otherwise, we join
        if [[ ! -f $JOINED_CLUSTER_SUCCESSFULLY && ${etcd_cluster//,/ } =~ (^| )$advertisement_ip( |$) ]]
        then
          create_cluster
        else
          join_cluster
        fi
}

verify_etcd_health_after_startup()
{
        # We could be in a bad state at this point - parse the etcd logs for
        # known error conditions. We do this from the logs as they're the most
        # reliable way of detecting that something is wrong.

        # We could have a data directory already, but not actually be a member of
        # the etcd cluster. Remove the data directory.
        tail -10 /var/log/clearwater-etcd/clearwater-etcd.log | grep -q "etcdserver: the member has been permanently removed from the cluster"
        if [[ $? == 0 ]]
        then
          echo "Etcd is in an inconsistent state - removing the data directory"
          rm -rf $DATA_DIR/$advertisement_ip
          exit 3
        fi

        # Wait for etcd to come up. Note - all this tests is that clearwater-etcd
        # is listening on 4000 - it doesn't confirm that etcd is running fully
        start_time=$(date +%s)
        while true; do
          if nc -z $listen_ip 4000; then
            touch $JOINED_CLUSTER_SUCCESSFULLY
            break;
          else
            current_time=$(date +%s)
            let "delta_time=$current_time - $start_time"
            if [ $delta_time -gt 60 ]; then
              echo "Etcd failed to come up - exiting"
              exit 2
            fi
            sleep 1
          fi
        done
}

verify_etcd_health_before_startup()
{
        # If we're already in the member list but are 'unstarted', remove our data dir, which
        # contains stale data from a previous unsuccessful startup attempt. This copes with a race
        # condition where member add succeeds but etcd doesn't then come up.
        #
        # The output of member list looks like:
        # <id>[unstarted]: name=xx-xx-xx-xx peerURLs=http://xx.xx.xx.xx:2380 clientURLs=http://xx.xx.xx.xx:4000
        # The [unstarted] is only present while the member hasn't fully joined the etcd cluster
        setup_etcdctl_peers
        member_list=$(/usr/bin/etcdctl member list)
        local_member_id=$(echo "$member_list" | grep -F -w "http://$local_ip:2380" | grep -o -E "^[^:]*" | grep -o "^[^[]\+")
        unstarted_member_id=$(echo "$member_list" | grep -F -w "http://$local_ip:2380" | grep "unstarted")
        if [[ $unstarted_member_id != '' ]]
        then
          /usr/bin/etcdctl member remove $local_member_id
          rm -rf $DATA_DIR/$advertisement_ip
        fi

        if [[ -e $DATA_DIR/$advertisement_ip ]]
        then
          # Check we can read our write-ahead log and snapshot files. If not, our
          # data directory is irrecoverably corrupt (perhaps because we ran out
          # of disk space and the files were half-written), so we should clean it
          # out and rejoin the cluster from scratch.
          timeout 5 /usr/bin/etcd-dump-logs --data-dir $DATA_DIR/$advertisement_ip > /dev/null 2>&1
          rc=$?

          if [[ $rc != 0 ]]
          then
            /usr/bin/etcdctl member remove $local_member_id
            rm -rf $DATA_DIR/$advertisement_ip
          fi
        fi
}

#
# Function that starts the daemon/service
#
do_start()
{
        # Return
        #   0 if daemon has been started
        #   1 if daemon was already running
        #   2 if daemon could not be started
        start-stop-daemon --start --quiet --pidfile $PIDFILE --name $NAME --startas $DAEMONWRAPPER --test > /dev/null \
                || return 1

        ETCD_NAME=${advertisement_ip//./-}
        CLUSTER_ARGS=

        # Make sure the data directory exists and is owned by the correct user
        mkdir -p $DATA_DIR
        chown $USER $DATA_DIR

        verify_etcd_health_before_startup

        if [ -n "$etcd_cluster" ] && [ -n "$etcd_proxy" ]
        then
          echo "Cannot specify both etcd_cluster and etcd_proxy"
          return 2
        elif [ -n "$etcd_cluster" ]
        then
          # Join or create the etcd cluster as a full member.

          if [[ -d $DATA_DIR/$advertisement_ip ]]
          then
            # We'll start normally using the data we saved off on our last boot.
            echo "Rejoining cluster..."
          else
            join_or_create_cluster
          fi

          # Add common clustering parameters
          CLUSTER_ARGS="$CLUSTER_ARGS
                        --initial-advertise-peer-urls http://$advertisement_ip:2380
                        --listen-peer-urls http://$listen_ip:2380"

        elif [ -n "$etcd_proxy" ]
        then
          # Run etcd as a proxy talking to the cluster.

          join_cluster_as_proxy
        else
          echo "Must specify either etcd_cluster or etcd_proxy"
          return 2
        fi

        # Allow us to write to the pidfile directory
        install -m 755 -o $NAME -g root -d /var/run/$NAME && chown -R $NAME /var/run/$NAME

        # Common arguments
        DAEMON_ARGS="--listen-client-urls http://0.0.0.0:4000
                     --advertise-client-urls http://$advertisement_ip:4000
                     --data-dir $DATA_DIR/$advertisement_ip
                     --name $ETCD_NAME
                     --debug"

        start-stop-daemon --start --quiet --background --pidfile $PIDFILE \
            --startas $DAEMONWRAPPER --chuid $USER -- $DAEMON_ARGS $CLUSTER_ARGS \
                || return 2

        verify_etcd_health_after_startup
}

#
# Function that stops the daemon/service
#
do_stop()
{
        # Return
        #   0 if daemon has been stopped
        #   1 if daemon was already stopped
        #   2 if daemon could not be stopped
        #   other if a failure occurred
        start-stop-daemon --stop --quiet --retry=TERM/30/KILL/5 --pidfile $PIDFILE --startas $DAEMONWRAPPER
        RETVAL="$?"
        [ "$RETVAL" = 2 ] && return 2
        # Wait for children to finish too if this is a daemon that forks
        # and if the daemon is only ever run from this initscript.
        # If the above conditions are not satisfied then add some other code
        # that waits for the process to drop all resources that could be
        # needed by services started subsequently.  A last resort is to
        # sleep for some time.
        #start-stop-daemon --stop --quiet --oknodo --retry=0/30/KILL/5 --startas $DAEMONWRAPPER
        [ "$?" = 2 ] && return 2
        # Many daemons don't delete their pidfiles when they exit.
        rm -f $PIDFILE
        return "$RETVAL"
}

#
# Function that aborts the daemon/service
#
# This is very similar to do_stop except it sends SIGABRT to dump a core file
# and waits longer for it to complete.
#
do_abort()
{
        # Return
        #   0 if daemon has been stopped
        #   1 if daemon was already stopped
        #   2 if daemon could not be stopped
        #   other if a failure occurred
        start-stop-daemon --stop --retry=ABRT/60/KILL/5 --pidfile $PIDFILE --startas $DAEMONWRAPPER
        RETVAL="$?"
        # If the abort failed, it may be because the PID in PIDFILE doesn't match the right process
        # In this window condition, we may not recover, so remove the PIDFILE to get it running
        if [ $RETVAL != 0 ]; then
          rm -f $PIDFILE
        fi
        return "$RETVAL"
}

#
# Function that decommissions an etcd instance
#
# This function should be used to permanently remove an etcd instance from the
# cluster.  Note that after this has been done, the operator may need to update
# the $etcd_cluster attribute before attempting to rejoin the cluster.
#
do_decommission()
{
        # Return
        #   0 if successful
        #   2 on error
        export ETCDCTL_PEERS=$advertisement_ip:4000
        health=$(/usr/bin/etcdctl cluster-health)
        if [[ $health =~ unhealthy ]]
        then
          echo Cannot decommission while cluster is unhealthy
          return 2
        fi

        id=$(/usr/bin/etcdctl member list | grep -F -w ${advertisement_ip//./-} | cut -f 1 -d :)
        if [[ -z $id ]]
        then
          echo Local node does not appear in the cluster
          return 2
        fi

        # etcdctl will stop the daemon automatically once it has removed the
        # local id (see https://coreos.com/etcd/docs/latest/runtime-configuration.html
        # "Remove a Member")
        /usr/bin/etcdctl member remove $id
        if [[ $? != 0 ]]
        then
          echo Failed to remove instance from cluster
          return 2
        fi

        rm -f $PIDFILE

        # Decommissioned so destroy the data directory and cluster files
        [[ -n $DATA_DIR ]] && [[ -n $advertisement_ip ]] && rm -rf $DATA_DIR/$advertisement_ip
        rm -f $JOINED_CLUSTER_SUCCESSFULLY
        rm -f $HEALTHY_CLUSTER_VIEW
}

#
# Function that sends a SIGHUP to the daemon/service
#
do_reload() {
        #
        # If the daemon can reload its configuration without
        # restarting (for example, when it is sent a SIGHUP),
        # then implement that here.
        #
        start-stop-daemon --stop --signal 1 --quiet --pidfile $PIDFILE --name $NAME
        return 0
}

# There should only be at most one etcd process, and it should be the one in /var/run/clearwater-etcd/clearwater-etcd.pid.
# Sanity check this, and kill and log any leaked ones.
if [ -f $PIDFILE ] ; then
  leaked_pids=$(pgrep -f "^$DAEMON" | grep -v $(cat $PIDFILE))
else
  leaked_pids=$(pgrep -f "^$DAEMON")
fi
if [ -n "$leaked_pids" ] ; then
  for pid in $leaked_pids ; do
    logger -p daemon.error -t $NAME Found leaked etcd $pid \(correct is $(cat $PIDFILE)\) - killing $pid
    kill -9 $pid
  done
fi

case "$1" in
  start)
        [ "$VERBOSE" != no ] && log_daemon_msg "Starting $DESC" "$NAME"
        do_start
        case "$?" in
                0|1) [ "$VERBOSE" != no ] && log_end_msg 0 ;;
                2) [ "$VERBOSE" != no ] && log_end_msg 1 ;;
        esac
        ;;
  stop)
        [ "$VERBOSE" != no ] && log_daemon_msg "Stopping $DESC" "$NAME"
        do_stop
        case "$?" in
                0|1) [ "$VERBOSE" != no ] && log_end_msg 0 ;;
                2) [ "$VERBOSE" != no ] && log_end_msg 1 ;;
        esac
        ;;
  status)
       status_of_proc "$DAEMON" "$NAME" && exit 0 || exit $?
       ;;
  #reload|force-reload)
        #
        # If do_reload() is not implemented then leave this commented out
        # and leave 'force-reload' as an alias for 'restart'.
        #
        #log_daemon_msg "Reloading $DESC" "$NAME"
        #do_reload
        #log_end_msg $?
        #;;
  restart|force-reload)
        #
        # If the "reload" option is implemented then remove the
        # 'force-reload' alias
        #
        log_daemon_msg "Restarting $DESC" "$NAME"
        do_stop
        case "$?" in
          0|1)
                do_start
                case "$?" in
                        0) log_end_msg 0 ;;
                        1) log_end_msg 1 ;; # Old process is still running
                        *) log_end_msg 1 ;; # Failed to start
                esac
                ;;
          *)
                # Failed to stop
                log_end_msg 1
                ;;
        esac
        ;;
  abort)
        log_daemon_msg "Aborting $DESC" "$NAME"
        do_abort
        ;;
  decommission)
        log_daemon_msg "Decommissioning $DESC" "$NAME"
        service clearwater-cluster-manager decommission || /bin/true
        service clearwater-queue-manager decommission || /bin/true
        service clearwater-config-manager decommission || /bin/true
        do_decommission
        ;;
  abort-restart)
        log_daemon_msg "Abort-Restarting $DESC" "$NAME"
        do_abort
        case "$?" in
          0|1)
                do_start
                case "$?" in
                        0) log_end_msg 0 ;;
                        1) log_end_msg 1 ;; # Old process is still running
                        *) log_end_msg 1 ;; # Failed to start
                esac
                ;;
          *)
                # Failed to stop
                log_end_msg 1
                ;;
        esac
        ;;
  *)
        echo "Usage: $SCRIPTNAME {start|stop|status|restart|force-reload|decommission}" >&2
        exit 3
        ;;
esac

:
