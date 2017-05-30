# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


from time import sleep
import constants
from .alarms import TooLongAlarm
from . import pdlogs
import logging

_log = logging.getLogger("cluster_manager.synchronization_fsm")


# Decorator to call a plugin function, and catch and log any exceptions it
# raises.
def safe_plugin(f, cluster_view, new_state=None):
    try:
        _log.info("Calling plugin method {}.{}".
                  format(f.__self__.__class__.__name__,
                         f.__name__))
        # Call into the plugin, and if it doesn't throw an exception,
        # return the state we should move into.
        f(cluster_view)
        return new_state
    except AssertionError: # pragma: no cover
        # Allow UT plugins to assert things, halt their FSM, and be noticed more
        # easily.
        raise
    except Exception as e:
        # If the plugin fails (which is unexpected), log the error and then
        # return None. This will keep this node in the same state, pausing the
        # scale-up (which will raise an alarm) until someone looks into it and
        # fixes the issue.
        _log.error("Call to {}.{} with cluster {} caused exception {!r}".
                   format(f.__self__.__class__.__name__,
                          f.__name__,
                          cluster_view,
                          e))
        return None


class SyncFSM(object):

    # The number of seconds to wait in WAITING_TO_JOIN/WAITING_TO_LEAVE state
    # before switching into JOINING/LEAVING state. Defined as a class constant
    # for easy overriding in UT.
    DELAY = 30

    def __init__(self, plugin, local_ip):
        self._plugin = plugin
        self._id = local_ip
        self._running = True
        self._startup = True
        self._alarm = TooLongAlarm()

    def quit(self):
        self._alarm.quit()

    def is_running(self):
        return self._running

    def _switch_all_to_joining(self, cluster_view):
        return {k: (constants.JOINING if v == constants.WAITING_TO_JOIN else v)
                for k, v in cluster_view.iteritems()}

    def _switch_all_to_leaving(self, cluster_view):
        return {k: (constants.LEAVING if v == constants.WAITING_TO_LEAVE else v)
                for k, v in cluster_view.iteritems()}

    def _log_joining_nodes(self, cluster_view):
        for node, state in cluster_view.iteritems():
            if state in [constants.JOINING, constants.JOINING_ACKNOWLEDGED_CHANGE]:
                pdlogs.NODE_JOINING.log(ip=node,
                                        cluster_desc=self._plugin.cluster_description())

    def _log_leaving_nodes(self, cluster_view):
        for node, state in cluster_view.iteritems():
            if state in [constants.LEAVING, constants.LEAVING_ACKNOWLEDGED_CHANGE]:
                pdlogs.NODE_LEAVING.log(ip=node,
                                        cluster_desc=self._plugin.cluster_description())

    def next(self, local_state, cluster_state, cluster_view):  # noqa
        """Main state machine function.

        Arguments:
            - local_state: string constant from constants.py
            - cluster_state: string constant from constants.py
            - cluster_view: dictionary of node IPs to local states

        Returns:
            - None if the state should not change
            - A string constant (from constants.py) representing the new local
            state of this node, if it wants to just change that
            - A dictionary of node IPs to states, representing the new state of
            the whole cluster, if it wants to change that
        """
        _log.info("Entered state machine for {} with local state {}, "
                  "cluster state {} and cluster view {}".format(
                      self._id,
                      local_state,
                      cluster_state,
                      cluster_view))
        assert(self._running)
        if self._startup:
            safe_plugin(self._plugin.on_startup,
                        cluster_view)
            self._startup = False

        # If we're mid-scale-up, ensure that the "scaling operation taking too
        # long" alarm is running, and cancel it if we're not
        if local_state == constants.NORMAL:
            self._alarm.cancel()
        elif self._plugin.should_be_in_cluster():
            self._alarm.trigger(self._id)

        # Handle the abnormal cases first - where the local node isn't in the
        # cluster, and where the local node is in ERROR state. These can happen
        # in any cluster state, so don't fit neatly into the main function body.

        if not self._plugin.should_be_in_cluster():
            # This plugin is just monitoring a remote cluster.
            if cluster_state in [constants.JOINING_CONFIG_CHANGING,
                                 constants.LEAVING_CONFIG_CHANGING]:
                # This branch is not guaranteed to be hit due to
                # https://github.com/Metaswitch/clearwater-etcd/issues/158.
                safe_plugin(self._plugin.on_cluster_changing, # pragma: no cover
                            cluster_view)
            elif cluster_state == constants.STABLE:
                safe_plugin(self._plugin.on_stable_cluster,
                            cluster_view)
            return None

        if local_state is None:
            if cluster_state in [constants.EMPTY, constants.STABLE, constants.JOIN_PENDING]:
                return constants.WAITING_TO_JOIN
            else:
                return None

        if local_state == constants.ERROR:
            return None

        # Main body of this function - define the action and next state for each
        # valid cluster state/local state pair.

        # If we're back in a stable state, and this node is a member of the
        # cluster, trigger the plugin to do whatever's necessary to refect that
        # (e.g. removing mid-scale-up config).

        elif (cluster_state == constants.STABLE and
                local_state == constants.NORMAL):
            return safe_plugin(self._plugin.on_stable_cluster,
                               cluster_view)
        elif (cluster_state == constants.STABLE_WITH_ERRORS and
                local_state == constants.NORMAL):
            return safe_plugin(self._plugin.on_stable_cluster,
                               cluster_view)

        # States for joining a cluster

        # If we're waiting to join, pause for SyncFSM.DELAY seconds (to allow
        # other new nodes to come online, and avoid repeating scale-up sveral
        # times), then move all WAITING_TO_JOIN nodes into JOINING state in
        # order to kick off scale-up.

        # Existing nodes (in NORMAL state) should do nothing.

        elif (cluster_state == constants.JOIN_PENDING and
                local_state == constants.WAITING_TO_JOIN):
            _log.info("Pausing for %d seconds in case more nodes are joining the cluster" % SyncFSM.DELAY)
            sleep(SyncFSM.DELAY)
            return self._switch_all_to_joining(cluster_view)
        elif (cluster_state == constants.JOIN_PENDING and
                local_state == constants.NORMAL):
            return None

        # STARTED_JOINING state involves everyone acknowledging that scale-up is
        # starting, so NORMAL or JOINING nodes should move into the relevant
        # ACKNOWLEDGED_CHANGE state. (Once they're in that state, they don't
        # have to do anything else until everyone has switched to that state, at
        # which point the cluster is in JOINING_CONFIG_CHANGING state).

        elif (cluster_state == constants.STARTED_JOINING and
                local_state == constants.JOINING_ACKNOWLEDGED_CHANGE):
            return None
        elif (cluster_state == constants.STARTED_JOINING and
                local_state == constants.NORMAL_ACKNOWLEDGED_CHANGE):
            return None
        elif (cluster_state == constants.STARTED_JOINING and
                local_state == constants.NORMAL):
            self._log_joining_nodes(cluster_view)
            return constants.NORMAL_ACKNOWLEDGED_CHANGE
        elif (cluster_state == constants.STARTED_JOINING and
                local_state == constants.JOINING):
            self._log_joining_nodes(cluster_view)
            return constants.JOINING_ACKNOWLEDGED_CHANGE

        # JOINING_CONFIG_CHANGING state starts when everyone has acknowledged
        # that scale-up is happening, and ends when everyone has updated their
        # config. So:
        # - Nodes in NORMAL_ACKNOWLEDGED_CHANGE/JOINING_ACKNOWLEDGED_CHANGE
        # should kick their plugin, and then move to the relevant
        # _CONFIG_CHANGED state.
        # - Nodes in NORMAL_CONFIG_CHANGED/JOINING_CONFIG_CHANGED state don't
        # have any more work to do in this phase

        elif (cluster_state == constants.JOINING_CONFIG_CHANGING and
                local_state == constants.JOINING_CONFIG_CHANGED):
            return None
        elif (cluster_state == constants.JOINING_CONFIG_CHANGING and
                local_state == constants.NORMAL_CONFIG_CHANGED):
            return None
        elif (cluster_state == constants.JOINING_CONFIG_CHANGING and
                local_state == constants.NORMAL_ACKNOWLEDGED_CHANGE):
            return safe_plugin(self._plugin.on_cluster_changing,
                               cluster_view,
                               new_state=constants.NORMAL_CONFIG_CHANGED)
        elif (cluster_state == constants.JOINING_CONFIG_CHANGING and
                local_state == constants.JOINING_ACKNOWLEDGED_CHANGE):
            return safe_plugin(self._plugin.on_joining_cluster,
                               cluster_view,
                               new_state=constants.JOINING_CONFIG_CHANGED)

        # JOINING_RESYNCING state starts when everyone has updated their
        # config, and ends when everyone has resynchronised their data around
        # the cluster. So:
        # - Nodes in NORMAL_ACKNOWLEDGED_CHANGE/JOINING_ACKNOWLEDGED_CHANGE
        # state should call into their plugin to do the resync, and then move to
        # NORMAL state.
        # - Nodes in NORMAL state don't have any more work to do.

        elif (cluster_state == constants.JOINING_RESYNCING and
                local_state == constants.NORMAL):
            return None
        elif (cluster_state == constants.JOINING_RESYNCING and
                local_state == constants.NORMAL_CONFIG_CHANGED):
            return safe_plugin(self._plugin.on_new_cluster_config_ready,
                               cluster_view,
                               new_state=constants.NORMAL)
        elif (cluster_state == constants.JOINING_RESYNCING and
                local_state == constants.JOINING_CONFIG_CHANGED):
            return safe_plugin(self._plugin.on_new_cluster_config_ready,
                               cluster_view,
                               new_state=constants.NORMAL)

        # States for leaving a cluster

        # If we're waiting to leave, pause for SyncFSM.DELAY seconds (to allow
        # other leaving nodes to enter this state), then move all
        # WAITING_TO_LEAVE nodes into LEAVING state in order to kick off
        # scale-down.

        # Remaining nodes (in NORMAL state) should do nothing.
        elif (cluster_state == constants.LEAVE_PENDING and
                local_state == constants.WAITING_TO_LEAVE):
            _log.info("Pausing for %d seconds in case more nodes are leaving the cluster" % SyncFSM.DELAY)
            sleep(SyncFSM.DELAY)
            return self._switch_all_to_leaving(cluster_view)
        elif (cluster_state == constants.LEAVE_PENDING and
                local_state == constants.NORMAL):
            return None

        # STARTED_LEAVING state involves everyone acknowledging that scale-down
        # is starting, so NORMAL or LEAVING nodes should move into the relevant
        # ACKNOWLEDGED_CHANGE state. (Once they're in that state, they don't
        # have to do anything else until everyone has switched to that state, at
        # which point the cluster is in LEAVING_CONFIG_CHANGING state).

        elif (cluster_state == constants.STARTED_LEAVING and
                local_state == constants.LEAVING_ACKNOWLEDGED_CHANGE):
            return None
        elif (cluster_state == constants.STARTED_LEAVING and
                local_state == constants.NORMAL_ACKNOWLEDGED_CHANGE):
            return None
        elif (cluster_state == constants.STARTED_LEAVING and
                local_state == constants.NORMAL):
            self._log_leaving_nodes(cluster_view)
            return constants.NORMAL_ACKNOWLEDGED_CHANGE
        elif (cluster_state == constants.STARTED_LEAVING and
                local_state == constants.LEAVING):
            self._log_leaving_nodes(cluster_view)
            return constants.LEAVING_ACKNOWLEDGED_CHANGE

        # LEAVING_CONFIG_CHANGING state starts when everyone has acknowledged
        # that scale-down is happening, and ends when everyone has updated their
        # config. So:
        # - Nodes in NORMAL_ACKNOWLEDGED_CHANGE/LEAVING_ACKNOWLEDGED_CHANGE
        # should kick their plugin, and then move to the relevant
        # _CONFIG_CHANGED state.
        # - Nodes in NORMAL_CONFIG_CHANGED/LEAVING_CONFIG_CHANGED state don't
        # have any more work to do in this phase

        elif (cluster_state == constants.LEAVING_CONFIG_CHANGING and
                local_state == constants.NORMAL_CONFIG_CHANGED):
                return None
        elif (cluster_state == constants.LEAVING_CONFIG_CHANGING and
                local_state == constants.LEAVING_CONFIG_CHANGED):
                return None
        elif (cluster_state == constants.LEAVING_CONFIG_CHANGING and
                local_state == constants.NORMAL_ACKNOWLEDGED_CHANGE):
            return safe_plugin(self._plugin.on_cluster_changing,
                               cluster_view,
                               new_state=constants.NORMAL_CONFIG_CHANGED)
        elif (cluster_state == constants.LEAVING_CONFIG_CHANGING and
                local_state == constants.LEAVING_ACKNOWLEDGED_CHANGE):
            return safe_plugin(self._plugin.on_cluster_changing,
                               cluster_view,
                               new_state=constants.LEAVING_CONFIG_CHANGED)

        # LEAVING_RESYNCING state starts when everyone has updated their
        # config, and ends when everyone has resynchronised their data around
        # the cluster. So:
        # - Nodes in NORMAL_ACKNOWLEDGED_CHANGE/LEAVING_ACKNOWLEDGED_CHANGE
        # state should call into their plugin to do the resync, and then move to
        # NORMAL state.
        # - Nodes in NORMAL or FINISHED state don't have any more work to do.

        elif (cluster_state == constants.LEAVING_RESYNCING and
                local_state == constants.NORMAL):
            return None
        elif (cluster_state == constants.LEAVING_RESYNCING and
                local_state == constants.FINISHED):
            return None
        elif (cluster_state == constants.LEAVING_RESYNCING and
                local_state == constants.LEAVING_CONFIG_CHANGED):
            return safe_plugin(self._plugin.on_new_cluster_config_ready,
                               cluster_view,
                               new_state=constants.FINISHED)
        elif (cluster_state == constants.LEAVING_RESYNCING and
                local_state == constants.NORMAL_CONFIG_CHANGED):
            return safe_plugin(self._plugin.on_new_cluster_config_ready,
                               cluster_view,
                               new_state=constants.NORMAL)

        # In FINISHED_LEAVING state, everyone is in NORMAL state (if they're
        # remaining, in which case they should do nothing) or FINISHED state (if
        # they're done, in which case they kick their plugin and then leave the
        # cluster.

        elif (cluster_state == constants.FINISHED_LEAVING and
                local_state == constants.NORMAL):
            # Not guaranteed to hit this state, as the 'finished' nodes could
            # all leave before the non-leaving nodes spot that state transition
            return None # pragma: no cover
        elif (cluster_state == constants.FINISHED_LEAVING and
                local_state == constants.FINISHED):
            # This node is finished, so this state machine (and this thread)
            # should stop.
            self._running = False
            return safe_plugin(self._plugin.on_leaving_cluster,
                               cluster_view,
                               new_state=constants.DELETE_ME)

        # Any valid state should have caused me to return by now
        _log.error("Invalid state in state machine for {} - local state {}, "
                   "cluster state {} and cluster view {}".format(
                       self._id,
                       local_state,
                       cluster_state,
                       cluster_view))
        return None
