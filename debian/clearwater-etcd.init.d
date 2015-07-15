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
PIDFILE=/var/run/$NAME.pid
DAEMON=/usr/bin/etcd
DAEMONWRAPPER=/usr/bin/etcdwrapper

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

create_cluster()
{
        # Creating a new cluster
        echo Creating new cluster...

        # Build the initial cluster view string based on the IP addresses in
        # $etcd_cluster.  Each entry looks like <name>=<peer url>.
        ETCD_INITIAL_CLUSTER=
        OLD_IFS=$IFS
        IFS=,
        for server in $etcd_cluster
        do
            server_name=${server%:*}
            server_name=${server_name//./-}
            ETCD_INITIAL_CLUSTER="${server_name}=http://$server:2380,$ETCD_INITIAL_CLUSTER"
        done
        IFS=$OLD_IFS

        CLUSTER_ARGS="--initial-cluster $ETCD_INITIAL_CLUSTER
                      --initial-cluster-state new"
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

        # Build the client list based on $etcd_cluster, each entry is simply
        # <IP>:<port> using the client port.
        export ETCDCTL_PEERS=
        OLD_IFS=$IFS
        IFS=,
        for server in $etcd_cluster
        do
            ETCDCTL_PEERS="$server:4000,$ETCDCTL_PEERS"
        done
        IFS=$OLD_IFS

	# Check to make sure the cluster we want to join is healthy.
	# If it's not, refuse to try joining. We do this because
	# observation indicate that doing so may cause problems in the
	# existing cluster, so to be on the safe side we check before
	# joining. Besides joining an unhealthy cluster is not likely
	# to work anyway, so why bother trying.
	/usr/bin/etcdctl cluster-health 2>&1 | grep "cluster is healthy"
        if [ $? -ne 0 ]
        then
          echo "Not joining an unhealthy cluster"
          exit 2
        fi

        # Tell the cluster we're joining, this prints useful environment
        # variables to stdout but also prints a success message so strip that
        # out before saving the variables to the temp file.
        # If we're already in the member list, remove ourselves first
        member=$(/usr/bin/etcdctl member list | grep ${management_local_ip:-$local_ip} | cut -f1 -d:)
        if [[ $member != '' ]]
        then
          /usr/bin/etcdctl member remove $member
          if [[ $? != 0 ]]
          then
            echo "Failed to remove local node from cluster"
            exit 2
          elif [[ -d $DATA_DIR/$advertisement_ip ]]
          then 
            rm -r $DATA_DIR/$advertisement_ip
          fi 
        fi
        
        /usr/bin/etcdctl member add $ETCD_NAME http://$advertisement_ip:2380 | grep -v "Added member" >> $TEMP_FILE
        if [[ $? != 0 ]]
        then
          echo "Failed to add local node to cluster"
          exit 2
        fi

        # Load the environment variables back into the local shell and export
        # them so ./etcd can see them when it starts up.
        . $TEMP_FILE
        CLUSTER_ARGS="--initial-cluster $ETCD_INITIAL_CLUSTER
                      --initial-cluster-state $ETCD_INITIAL_CLUSTER_STATE"

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
        if [[ $etcd_cluster =~ (^|,)$advertisement_ip(,|$) ]]
        then
          create_cluster
        else
          join_cluster
        fi
}

wait_for_etcd()
{
        # Wait for etcd to come up, but timeout after 60 seconds
        stm=$(date +%s)
        while true; do
          if nc -z $listen_ip 4000; then
            break;
          else
	    ctm=$(date +%s)
	    let "dtm=$ctm - $stm"
	    if [ $dtm -gt 60 ]; then
		echo "Etcd fail to come up"
		exit 2
	    fi
            sleep 1
          fi
        done
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
        if [[ -d $DATA_DIR/$advertisement_ip ]]
        then
          # We'll start normally using the data we saved off on our last boot.
          echo "Rejoining cluster..."
        else
          # Exit if the etcd_cluster value hasn't been set
          if [ -z "$etcd_cluster" ]
          then
            echo "Can't start clearwater-etcd without a etcd_cluster setting in /etc/clearwater/config"
            return 2
          fi

          join_or_create_cluster
	  # Lose the race by delaying... I don't like delaying, but I couldn't
	  # determine anything concrete to wait for. There's some kind of
	  # race between adding ourselves as a member and starting the daemon.
	  # If the daemon comes up too fast, it will fail with an error
	  # like this:
	  #     2015/06/20 07:54:38 etcd: error validating peerURLs 192-168-165-80=http://192.168.165.80:2380,192-168-165-81=http://192.168.165.81:2380,192-168-165-82=http://192.168.165.82:2380,192-168-165-84=http://192.168.165.84:2380,=http://192.168.165.85:2380: member count is unequal
	  # After that error, monit will restart the daemon and the cycle
	  # continues forever, never recovering.
	  sleep 5
        fi

        # Common arguments
        DAEMON_ARGS="--listen-client-urls http://$listen_ip:4000
                     --advertise-client-urls http://$advertisement_ip:4000
                     --listen-peer-urls http://$listen_ip:2380
                     --initial-advertise-peer-urls http://$advertisement_ip:2380
                     --data-dir $DATA_DIR/$advertisement_ip
                     --name $ETCD_NAME"

        start-stop-daemon --start --quiet --background --make-pidfile --pidfile $PIDFILE --startas $DAEMONWRAPPER --chuid $NAME -- $DAEMON_ARGS $CLUSTER_ARGS \
                || return 2

        wait_for_etcd

        # See that etcd stays up for more than a few seconds. There have been times when
	# we get into an infinite loop restarting etcd when its configuration
	# won't allow it to come up. The following looks for a specific error
	# at the end of etcd's log file and if it's there, we'll take action and
	# prevent the loop from continuing.
        for i in {1..5}; do
          if ! nc -z $listen_ip 4000; then
	    if tail -1 /var/log/clearwater-etcd/clearwater-etcd.log | grep -q "etcdserver: the data-dir used by this member must be removed[.]"; then
		echo "etcd didn't stay up due to data-dir error - removing it..."
		rm -rf $DATA_DIR/$advertisement_ip
		break;
	    fi
          else
            sleep 1
          fi
        done
}

do_rebuild()
{
        # Return
        #   0 if daemon has been started
        #   1 if daemon was already running
        #   2 if daemon could not be started
        start-stop-daemon --start --quiet --pidfile $PIDFILE --name $NAME --startas $DAEMONWRAPPER --test > /dev/null \
                || (echo "Cannot recreate cluster while etcd is running; stop it first" && return 1)

        ETCD_NAME=${advertisement_ip//./-}
        create_cluster

        # Standard ports
        DAEMON_ARGS="--listen-client-urls http://$listen_ip:4000
                     --advertise-client-urls http://$advertisement_ip:4000
                     --listen-peer-urls http://$listen_ip:2380
                     --initial-advertise-peer-urls http://$advertisement_ip:2380
                     --data-dir $DATA_DIR/$advertisement_ip
                     --name $ETCD_NAME
                     --force-new-cluster"

        start-stop-daemon --start --quiet --background --make-pidfile --pidfile $PIDFILE --startas $DAEMONWRAPPER --chuid $NAME -- $DAEMON_ARGS $CLUSTER_ARGS \
                || return 2

        wait_for_etcd
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
        [ "$RETVAL" = 2 ] && return 2
        # Many daemons don't delete their pidfiles when they exit.
        rm -f $PIDFILE
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

        id=$(/usr/bin/etcdctl member list | grep ${advertisement_ip//./-} | cut -f 1 -d :)
        if [[ -z $id ]]
        then
          echo Local node does not appear in the cluster
          return 2
        fi

        /usr/bin/etcdctl member remove $id
        if [[ $? != 0 ]]
        then
          echo Failed to remove instance from cluster
          return 2
        fi

        start-stop-daemon --stop --retry=USR2/60/KILL/5 --pidfile $PIDFILE --startas $DAEMONWRAPPER
        RETVAL=$?
        [[ $RETVAL == 2 ]] && return 2

        rm -f $PIDFILE

        # Decommissioned so destroy the data directory
        [[ -n $DATA_DIR ]] && [[ -n $advertisement_ip ]] && rm -rf $DATA_DIR/$advertisement_ip
}

#
# Function that decommissions an etcd instance
#
# This function should be used to permanently and forcibly remove an etcd instance from a broken
# cluster.
#
do_force_decommission()
{
        # Return
        #   0 if successful
        #   2 on error
        start-stop-daemon --stop --retry=USR2/60/KILL/5 --pidfile $PIDFILE --startas $DAEMONWRAPPER
        RETVAL=$?
        [[ $RETVAL == 2 ]] && return 2

        [[ -n $PIDFILE ]] && rm -f $PIDFILE

        # Decommissioned so destroy the data directory
        [[ -n $DATA_DIR ]] && [[ -n $advertisement_ip ]] && rm -rf $DATA_DIR/$advertisement_ip
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
        service clearwater-config-manager decommission || /bin/true
        do_decommission
        ;;
  force-decommission)
        echo "Forcibly decommissioning $DESC on $public_hostname."
        echo
        echo "This should only be done when following the documented disaster "
        echo "recovery process. It deletes data from this node, so you should "
        echo "make sure you have:"
        echo
        echo "* confirmed that the etcd_cluster setting in "
        echo "/etc/clearwater/config ($etcd_cluster) is correct"
        echo "* created a working one-node cluster to begin the recovery process"
        echo 
        echo "Do you want to proceed with this decommission? [y/N]"
        read -r REPLY
        if [[ $REPLY = "y" ]]
        then
          log_daemon_msg "Continuing to forcibly decommission $DESC" "$NAME"
          do_force_decommission
        fi
        ;;
  force-new-cluster)
        echo "Forcibly recreating a cluster for $DESC on $public_hostname."
        echo
        echo "This should only be done when following the documented disaster "
        echo "recovery process. It deletes the etcd cluster configuration from "
        echo "this node, so you should make sure you have:"
        echo
        echo "* confirmed that the etcd_cluster setting in "
        echo "/etc/clearwater/local_config ($etcd_cluster) is correct"
        echo 
        echo "Do you want to proceed with this rebuild? [y/N]"
        read -r REPLY
        if [[ $REPLY = "y" ]]
        then
          log_daemon_msg "Continuing to forcibly recreate cluster for $DESC" "$NAME"
          do_rebuild
        fi

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
        echo "Usage: $SCRIPTNAME {start|stop|status|restart|force-reload|decommission|force-decommission|force-new-cluster}" >&2
        exit 3
        ;;
esac

:
