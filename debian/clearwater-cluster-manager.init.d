#!/bin/sh

# @file clearwater-cluster-manager.init.d
#
# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

### BEGIN INIT INFO
# Provides:          clearwater-cluster-manager
# Required-Start:    $network $local_fs
# Required-Stop:
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: clearwater-cluster-manager
# Description:       clearwater-cluster-manager
### END INIT INFO

# PATH should only include /usr/* if it runs after the mountnfs.sh script
PATH=/sbin:/usr/sbin:/bin:/usr/bin
DESC=clearwater-cluster-manager       # Introduce a short description here
NAME=clearwater-cluster-manager       # Introduce the short server's name here (not suitable for --name)
USER=clearwater-cluster-manager       # Username to run as
DAEMON_DIR=/usr/share/clearwater/clearwater-cluster-manager/
PIDFILE=/var/run/$NAME.pid
SCRIPTNAME=/etc/init.d/$NAME

# We have separate entries for DAEMON and ACTUAL_EXEC:
# - DAEMON is the command to run to start clearwater-cluster-manager. We use this when we want to
# start it.
# - ACTUAL_EXEC is the name which will appear in the process tree after it's been started. We use
# this when we want to locate currently running instances (to kill them, send a signal to them, or
# to check if they exist before starting a new process).
#
# See also start-stop-daemon's manpage, specifically the comment on --exec: "this might not work as
# intended with interpreted scripts, as the executable will point to the interpreter".
DAEMON=/usr/share/clearwater/bin/clearwater-cluster-manager
ACTUAL_EXEC=/usr/share/clearwater/clearwater-cluster-manager/env/bin/python

# Exit if the package is not installed
[ -x $DAEMON ] || exit 0
[ -x $ACTUAL_EXEC ] || exit 0

# Read configuration variable file if it is present
[ -r /etc/default/$NAME ] && . /etc/default/$NAME

# Load the VERBOSE setting and other rcS variables
. /lib/init/vars.sh

# Define LSB log_* functions.
# Depend on lsb-base (>= 3.0-6) to ensure that this file is present.
. /lib/lsb/init-functions

#
# Function that starts the daemon/service
#
do_start()
{
  # Return
  #   0 if daemon has been started
  #   1 if daemon was already running
  #   2 if daemon could not be started

  if [ -e /etc/clearwater/no_cluster_manager ]
  then
    echo "/etc/clearwater/no_cluster_manager exists, not starting cluster manager"
    return 2
  fi

  # Make sure to pull in the node_type files before local_config
  local_site_name=site1
  remote_site_name=""
  remote_cassandra_seeds=""
  signaling_namespace=""
  etcd_key=clearwater
  etcd_cluster_key=""
  log_level=3
  log_directory=/var/log/clearwater-cluster-manager
  cluster_manager_enabled="Y"

  # This sets up $uuid - it's created by /usr/share/clearwater/infrastructure/scripts/node_identity
  . /etc/clearwater/node_identity

  if [ -d /usr/share/clearwater/node_type.d ]
  then
    . /usr/share/clearwater/node_type.d/$(ls /usr/share/clearwater/node_type.d | head -n 1)
  fi
  . /etc/clearwater/config

  if [ -z "$local_ip" ]
  then
    echo "/etc/clearwater/local_config not provided, not starting"
    return 3
  fi

  DAEMON_ARGS="--mgmt-local-ip=${management_local_ip:-$local_ip}
               --sig-local-ip=$local_ip
               --local-site=$local_site_name
               --remote-site=$remote_site_name
               --remote-cassandra-seeds=$remote_cassandra_seeds
               --signaling-namespace=$signaling_namespace
               --uuid=$uuid
               --etcd-key=$etcd_key
               --etcd-cluster-key=$etcd_cluster_key
               --cluster-manager-enabled=$cluster_manager_enabled
               --log-level=$log_level
               --log-directory=$log_directory
               --pidfile=$PIDFILE"

  # Check if the process is already running - we use ACTUAL_EXEC here, as that's what will be in the
  # process tree (not DAEMON).
  start-stop-daemon --start --quiet --pidfile $PIDFILE --exec $ACTUAL_EXEC --test > /dev/null \
    || return 1

  start-stop-daemon --start --quiet --chdir $DAEMON_DIR --pidfile $PIDFILE --exec $ACTUAL_EXEC --startas $DAEMON -- $DAEMON_ARGS \
    || return 2
  # Add code here, if necessary, that waits for the process to be ready
  # to handle requests from services started subsequently which depend
  # on this one.  As a last resort, sleep for some time.
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
	start-stop-daemon --stop --quiet --retry=TERM/30/KILL/5 --exec $ACTUAL_EXEC --pidfile $PIDFILE
	RETVAL="$?"
	return "$RETVAL"
}

#
# Function that decommissions the daemon/service
#
do_decommission()
{
	# Return
	#   0 if daemon has been stopped
	#   1 if daemon was already stopped
	#   2 if daemon could not be stopped within 20 minutes
	#   other if a failure occurred
	start-stop-daemon --stop --quiet --retry=QUIT/1200 --exec $ACTUAL_EXEC --pidfile $PIDFILE
	RETVAL="$?"
	return "$RETVAL"
}


#
# Function that aborts the daemon/service
#
# This is very similar to do_stop except it sends SIGUSR1 to dump a stack.
#
do_abort()
{
        # Return
        #   0 if daemon has been stopped
        #   1 if daemon was already stopped
        #   2 if daemon could not be stopped
        #   other if a failure occurred
        start-stop-daemon --stop --quiet --retry=USR1/5/TERM/30/KILL/5 --exec $ACTUAL_EXEC --pidfile $PIDFILE
        RETVAL="$?"
        # If the abort failed, it may be because the PID in PIDFILE doesn't match the right process
        # In this window condition, we may not recover, so remove the PIDFILE to get it running
        if [ $RETVAL != 0 ]; then
          rm -f $PIDFILE
        fi
        return "$RETVAL"
}

# There should only be at most one cluster-manager process, and it should be the one in /var/run/clearwater-cluster-manager.pid.
# Sanity check this, and kill and log any leaked ones.
if [ -f $PIDFILE ] ; then
  leaked_pids=$(pgrep -f "^$DAEMON" | grep -v $(cat $PIDFILE))
else
  leaked_pids=$(pgrep -f "^$DAEMON")
fi
if [ -n "$leaked_pids" ] ; then
  for pid in $leaked_pids ; do
    logger -p daemon.error -t $NAME Found leaked cluster-manager $pid \(correct is $(cat $PIDFILE)\) - killing $pid
    kill -9 $pid
  done
fi

case "$1" in
  start)
    [ "$VERBOSE" != no ] && log_daemon_msg "Starting $DESC " "$NAME"
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
	echo "Usage: $SCRIPTNAME {start|stop|status|restart|force-reload|abort|abort-restart|decommission}" >&2
	exit 3
	;;
esac

:
