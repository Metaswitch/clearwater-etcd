#!/bin/bash

# @file clearwater-etcd.init.d
#
# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

### BEGIN INIT INFO
# Provides:          clearwater-etcd
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Default-Start:
# Default-Stop:
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
LOCKFILE_DIR=/var/run/$NAME
LOCKFILE=$LOCKFILE_DIR/$NAME-initd.lock
USER=$NAME
LOG_FILE=/var/log/clearwater-etcd/clearwater-etcd-initd.log

# Default the etcd version to the latest supported etcd version.
etcd_version=3.1.7
. /etc/clearwater/config

DAEMON=/usr/share/clearwater/clearwater-etcd/$etcd_version/etcd
DAEMONWRAPPER=/usr/share/clearwater/clearwater-etcd/$etcd_version/etcdwrapper
MYPID=$$

# Log parameters at "debug" level. These are just written to the log file (with
# timestamps).
log_debug() {
  echo $(date +'%Y-%m-%d %H:%M:%S.%N') "[$MYPID]" "$@" >> $LOG_FILE
}

# Log parameters at "info" level. These are written to the console (without
# timestamps) and also to the log file (with them)
log_info() {
  echo "$@"
  log_debug "$@"
}

# Waits up to 60 seconds to lock $LOCKFILE, returning 0 if it succeeds and 1 if
# it fails
lock() {
  mkdir -p $LOCKFILE_DIR
  # 300 is an arbitrarily-chosen file descriptor number
  exec 300> $LOCKFILE

  log_debug "Attempting to acquire lock on $LOCKFILE with 60-second timeout"
  flock --wait 60 300

  if [[ $? == 0 ]]
  then
    log_debug "Successfully acquired lock on $LOCKFILE"
    return 0
  else
    log_debug "Failed to acquire lock on $LOCKFILE"
    return 1
  fi
}

# Wrapper that runs etcdctl but also logs the following to the log file:
# - The etcdctl command being run
# - stdout and stderr from the command
# - The status code from the command
etcdctl_wrapper() {
  log_debug "Running etcdctl $@"

  # Run the etcdctl command and capture stdout and stderr to the log file.
  #
  # The redirections in this command are a bit insane:
  # a)  Make file descriptor 7 a copy of the original stdout
  # b)  Redirect stdout to the original stderr.
  # c)  Redirect stderr to a temporary FD that is passed to the stdin of a tee
  #     subcommand. This writes all its input to the log file and to the stdout
  #     inherited from its parent. But the parent stdout is currently pointing
  #     at the original stderr.
  # d)  Restore stdout to the original stdout (currently pointed to by FD 7).
  # e)  Redirect stdout to another tee command. This command's stdout is the
  #     original stdout.
  # f)  We're done with FD 7, so close it.
  #
  # The end result of all this is that the stdout and stderr of the etcdctl
  # command go to same place as if we hadn't done any of this, but they are also
  # captured to the log file.
  #
  # We also save off the status code from etcdctl so it can be logged and
  # returned. Despite all our shenanigans we've only run one command in this
  # shell, so $? does indeed contain the exit code from etcdctl.
  /usr/share/clearwater/clearwater-etcd/$etcd_version/etcdctl "$@" \
    7>&1 \
    1>&2 \
    2> >(tee -a $LOG_FILE) \
    1>&7 \
    1> >(tee -a $LOG_FILE) \
    7>&-
  retcode=$?

  log_debug "etcdctl returned $retcode"

  return $retcode
}

# Exit if the package is not installed
if [ ! -x "$DAEMON" ]; then
  log_info "Invalid etcd version: valid versions are 3.1.7 (recommended) and 2.2.5"
  exit 0
fi

# Read configuration variable file if it is present
#[ -r /etc/default/$NAME ] && . /etc/default/$NAME

# Load the VERBOSE setting and other rcS variables
. /lib/init/vars.sh

# Define LSB log_* functions.
# Depend on lsb-base (>= 3.2-14) to ensure that this file is present
# and status_of_proc is working.
. /lib/lsb/init-functions

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
        log_info "Creating new cluster..."

        # Build the initial cluster view string based on the IP addresses in
        # $etcd_cluster.
        generate_initial_cluster $etcd_cluster

        CLUSTER_ARGS="--initial-cluster $ETCD_INITIAL_CLUSTER
                      --initial-cluster-state new"
}

join_cluster_as_proxy()
{
        log_info "Joining cluster as proxy..."

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

          # We also want to ensure that the file was not just empty, so verify
          # that stripping white space still leaves something
          if [[ -z "${healthy_cluster// /}" ]]
          then
            log_debug "healthy cluster view was empty, using config values instead"
          else
            # Set etcd_cluster or etcd_proxy to the values we found in the
            # healthy cluster view, based on what is provided in config
            if [ -n "$etcd_cluster" ]
            then
              etcd_cluster=$healthy_cluster
            elif [ -n "$etcd_proxy" ]
            then
              etcd_proxy=$healthy_cluster
            fi
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

        log_debug "Configured ETCDCTL_PEERS: $ETCDCTL_PEERS"
}


join_cluster()
{
        # Joining existing cluster
        log_info "Joining existing cluster..."

        # If this fails, then hold off trying again for a time. This stops us
        # overwhelming the etcd elections on a large scale-up.
        sleep $[$RANDOM%30]

        # We need a temp file to deal with the environment variables.
        TEMP_FILE=$(mktemp)

        setup_etcdctl_peers

        # Check to make sure the cluster we want to join is healthy.
        # If it's not, don't even try joining (it won't work, and may
        # cause problems with the cluster)
        log_debug "Check cluster is healthy"
        etcdctl_wrapper cluster-health 2>&1 | grep "cluster is healthy"
        if [ $? -ne 0 ]
         then
           log_info "Not joining an unhealthy cluster"
           exit 2
        fi

        # Tell the cluster we're joining
        log_debug "Tell the cluster we're joining"
        etcdctl_wrapper member add $ETCD_NAME http://$advertisement_ip:2380
        if [[ $? != 0 ]]
        then
          local_member_id=$(etcdctl_wrapper member list | grep -F -w "http://$advertisement_ip:2380" | grep -o -E "^[^:]*" | grep -o "^[^[]\+")
          etcdctl_wrapper member remove $local_member_id
          rm -rf $DATA_DIR/$advertisement_ip
          log_info "Failed to add local node $advertisement_ip to the etcd cluster"
          logger -p daemon.error -t $NAME Failed to add the local node \($advertisement_ip\) to the etcd cluster
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
        log_debug "Check we're actually a member of the cluster"
        tail -10 /var/log/clearwater-etcd/clearwater-etcd.log | grep -q "etcdserver: the member has been permanently removed from the cluster"
        if [[ $? == 0 ]]
        then
          log_info "Etcd is in an inconsistent state - removing the data directory"
          logger -p daemon.error -t $NAME Etcd is in an inconsistent state - removing the data directory
          rm -rf $DATA_DIR/$advertisement_ip
          exit 3
        fi

        # Wait for etcd to come up. Note - all this tests is that clearwater-etcd
        # is listening on 4000 - it doesn't confirm that etcd is running fully
        log_debug "Wait for etcd to startup"

        start_time=$(date +%s)
        while true; do
          if nc -z $listen_ip 4000; then
            touch $JOINED_CLUSTER_SUCCESSFULLY
            break;
          else
            current_time=$(date +%s)
            let "delta_time=$current_time - $start_time"
            if [ $delta_time -gt 60 ]; then
              log_info "Etcd failed to start"
              logger -p daemon.error -t $NAME Etcd failed to start
              exit 2
            fi
            sleep 1
          fi
        done

        log_debug "Etcd started successfully"
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

        log_debug "Check for previous failed startup attempt"
        member_list=$(etcdctl_wrapper member list)
        local_member_id=$(echo "$member_list" | grep -F -w "http://$local_ip:2380" | grep -o -E "^[^:]*" | grep -o "^[^[]\+")
        unstarted_member_id=$(echo "$member_list" | grep -F -w "http://$local_ip:2380" | grep "unstarted")
        if [[ $unstarted_member_id != '' ]]
        then
          log_debug "Etcd failed to start successfully on a previous attempt - removing the data directory"
          logger -p daemon.error -t $NAME Etcd failed to start successfully on a previous attempt - removing the data directory

          etcdctl_wrapper member remove $local_member_id
          rm -rf $DATA_DIR/$advertisement_ip
        fi

        if [[ -e $DATA_DIR/$advertisement_ip ]]
        then
          # Check we can read our write-ahead log and snapshot files. If not, our
          # data directory is irrecoverably corrupt (perhaps because we ran out
          # of disk space and the files were half-written), so we should clean it
          # out and rejoin the cluster from scratch.
          log_debug "Check we can read files in the data directory"
          timeout 5 /usr/share/clearwater/clearwater-etcd/$etcd_version/etcd-dump-logs --data-dir $DATA_DIR/$advertisement_ip > /dev/null 2>&1
          rc=$?

          if [[ $rc != 0 ]]
          then
            log_debug "The etcd data is corrupted - removing the data directory"
            logger -p daemon.error -t $NAME The etcd data is corrupted - removing the data directory
            etcdctl_wrapper member remove $local_member_id
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
        start-stop-daemon --start --quiet --pidfile $PIDFILE --name $(basename $DAEMON) --startas $DAEMONWRAPPER --test > /dev/null \
                || return 1

        ETCD_NAME=${advertisement_ip//./-}
        CLUSTER_ARGS=

        # Make sure the data directory exists and is owned by the correct user
        mkdir -p $DATA_DIR
        chown $USER $DATA_DIR

        verify_etcd_health_before_startup

        if [ -n "$etcd_cluster" ] && [ -n "$etcd_proxy" ]
        then
          log_info "Cannot specify both etcd_cluster and etcd_proxy"
          return 2
        elif [ -n "$etcd_cluster" ]
        then
          # Join or create the etcd cluster as a full member.

          if [[ -d $DATA_DIR/$advertisement_ip ]]
          then
            # We'll start normally using the data we saved off on our last boot.
            log_info "Rejoining cluster..."
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
          log_info "Must specify either etcd_cluster or etcd_proxy"
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

        log_debug "Starting etcd with: $DAEMON_ARGS $CLUSTER_ARGS"
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
        log_debug "Check cluster is healthy before decommissioning"
        export ETCDCTL_PEERS=$advertisement_ip:4000
        health=$(etcdctl_wrapper cluster-health)
        if [[ $health =~ unhealthy ]]
        then
          log_info "Cannot decommission while cluster is unhealthy"
          return 2
        fi

        log_debug "Check we are currently in the cluster"
        id=$(etcdctl_wrapper member list | grep -F -w ${advertisement_ip//./-} | cut -f 1 -d :)
        if [[ -z $id ]]
        then
          log_info "Local node does not appear in the cluster"
          return 2
        fi

        # etcdctl will stop the daemon automatically once it has removed the
        # local id (see https://coreos.com/etcd/docs/latest/runtime-configuration.html
        # "Remove a Member")
        log_debug "Remove ourselves from the cluster"
        etcdctl_wrapper member remove $id
        if [[ $? != 0 ]]
        then
          log_info "Failed to remove instance from cluster"
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
        start-stop-daemon --stop --signal 1 --quiet --pidfile $PIDFILE --name $(basename $DAEMON)
        return 0
}

log_debug "Invoked with argument '$1'"
log_debug "Process tree: " $(pstree -p -s $MYPID)

# We only want one instance of this init script to run at once, as it does
# things like 'member add' and 'member remove' which will be unsafe if
# duplicated.
lock || exit 1

# There should only be at most one etcd process, and it should be the one in /var/run/clearwater-etcd/clearwater-etcd.pid.
# Sanity check this, and kill and log any leaked ones.
if [ -f $PIDFILE ] ; then
  leaked_pids=$(pgrep -f "^$DAEMON" | grep -v $(cat $PIDFILE))
else
  leaked_pids=$(pgrep -f "^$DAEMON")
fi
if [ -n "$leaked_pids" ] ; then
  for pid in $leaked_pids ; do
    log_debug "Found leaked etcd $pid (correct is $(cat $PIDFILE)) - killing $pid"
    logger -p daemon.error -t $NAME Found leaked etcd $pid \(correct is $(cat $PIDFILE)\) - killing $pid
    kill -9 $pid
  done
fi

case "$1" in
  start)
        [ "$VERBOSE" != no ] && log_daemon_msg "Starting $DESC" "$NAME"
        log_debug "Starting $DESC" "$NAME"
        do_start
        case "$?" in
                0|1) [ "$VERBOSE" != no ] && log_end_msg 0 ;;
                2) [ "$VERBOSE" != no ] && log_end_msg 1 ;;
        esac
        ;;
  stop)
        [ "$VERBOSE" != no ] && log_daemon_msg "Stopping $DESC" "$NAME"
        log_debug "Stopping $DESC" "$NAME"
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
        log_debug "Restarting $DESC" "$NAME"
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
        log_debug "Aborting $DESC" "$NAME"
        do_abort
        ;;
  decommission)
        log_daemon_msg "Decommissioning the etcd processes"

        service clearwater-cluster-manager decommission
        if [ $? != 0 ]; then
          log_info "Failure: Unable to decommission the cluster manager"
          exit 1
        fi

        service clearwater-queue-manager decommission
        if [ $? != 0 ]; then
          log_info "Failure: Unable to decommission the queue manager"
          exit 1
        fi

        service clearwater-config-manager decommission
        if [ $? != 0 ]; then
          log_info "Failure: Unable to decommission the config manager"
          exit 1
        fi

        log_daemon_msg "Decommissioning etcd"
        if [ -n "$etcd_proxy" ]; then
          do_stop
        else
          do_decommission
        fi
        exit $?
        ;;
  abort-restart)
        log_daemon_msg "Abort-Restarting $DESC" "$NAME"
        log_debug "Abort-Restarting $DESC" "$NAME"
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
