from time import sleep
from .constants import *
from .alarms import TooLongAlarm
import logging

_log = logging.getLogger("cluster_manager.fsm")


def safe_plugin(f, cluster_view, new_state=None):
    try:
        f(cluster_view)
        return new_state
    except AssertionError:
        raise
    except Exception as e:
        _log.error("Call to {}.{} with cluster {} caused exception {!r}".
                   format(f.__self__.__class__.__name__,
                          f.__name__,
                          cluster_view,
                          e))
        return None


class SyncFSM(object):
    DELAY = 30

    def __init__(self, plugin, local_ip):
        self._plugin = plugin
        self._id = local_ip
        self._running = True
        self._alarm = TooLongAlarm()

    def quit(self):
        self._alarm.quit()

    def is_running(self):
        return self._running

    def _switch_all_to_joining(self, cluster_view):
        return {k: (JOINING if v == WAITING_TO_JOIN else v)
                for k, v in cluster_view.iteritems()}

    def _switch_all_to_leaving(self, cluster_view):
        return {k: (LEAVING if v == WAITING_TO_LEAVE else v)
                for k, v in cluster_view.iteritems()}

    def _switch_myself_to(self, new_state, cluster_view):
        cluster_view.update({self._id: new_state})
        return cluster_view

    def _delete_myself(self, cluster_view):
        return {k: v for k, v in cluster_view.iteritems() if k != self._id}

    def next(self, local_state, cluster_state, cluster_view):  # noqa
        _log.debug("Entered state machine for {} with local state {}, "
                   "cluster state {} and cluster view {}".format(
                       self._id,
                       local_state,
                       cluster_state,
                       cluster_view))
        assert(self._running)
        if local_state == NORMAL:
            self._alarm.cancel()
        else:
            self._alarm.trigger(self._id)

        # Handle the case where the local node isn't in the cluster first

        if local_state is None:
            if cluster_state == EMPTY:
                return NORMAL
            elif cluster_state in [STABLE, JOIN_PENDING]:
                return self._switch_myself_to(WAITING_TO_JOIN, cluster_view)
            else:
                return None

        elif (cluster_state == STABLE and
                local_state == NORMAL):
            return safe_plugin(self._plugin.on_stable_cluster,
                               cluster_view)
        elif (cluster_state == STABLE_WITH_ERRORS and
                local_state == NORMAL):
            return safe_plugin(self._plugin.on_stable_cluster,
                               cluster_view)

        # States for joining a cluster

        elif (cluster_state == JOIN_PENDING and
                local_state == WAITING_TO_JOIN):
            sleep(SyncFSM.DELAY)
            return self._switch_all_to_joining(cluster_view)
        elif (cluster_state == JOIN_PENDING and
                local_state == NORMAL):
            return None

        elif (cluster_state == STARTED_JOINING and
                local_state == JOINING_ACKNOWLEDGED_CHANGE):
            return None
        elif (cluster_state == STARTED_JOINING and
                local_state == NORMAL_ACKNOWLEDGED_CHANGE):
            return None
        elif (cluster_state == STARTED_JOINING and
                local_state == NORMAL):
            return NORMAL_ACKNOWLEDGED_CHANGE
        elif (cluster_state == STARTED_JOINING and
                local_state == JOINING):
            return JOINING_ACKNOWLEDGED_CHANGE

        elif (cluster_state == JOINING_CONFIG_CHANGING and
                local_state == JOINING_CONFIG_CHANGED):
            return None
        elif (cluster_state == JOINING_CONFIG_CHANGING and
                local_state == NORMAL_CONFIG_CHANGED):
            return None
        elif (cluster_state == JOINING_CONFIG_CHANGING and
                local_state == NORMAL_ACKNOWLEDGED_CHANGE):
            return safe_plugin(self._plugin.on_cluster_changing,
                               cluster_view,
                               new_state=NORMAL_CONFIG_CHANGED)
        elif (cluster_state == JOINING_CONFIG_CHANGING and
                local_state == JOINING_ACKNOWLEDGED_CHANGE):
            return safe_plugin(self._plugin.on_cluster_changing,
                               cluster_view,
                               new_state=JOINING_CONFIG_CHANGED)

        elif (cluster_state == JOINING_RESYNCING and
                local_state == NORMAL):
            return None
        elif (cluster_state == JOINING_RESYNCING and
                local_state == NORMAL_CONFIG_CHANGED):
            return safe_plugin(self._plugin.on_new_cluster_config_ready,
                               cluster_view,
                               new_state=NORMAL)
        elif (cluster_state == JOINING_RESYNCING and
                local_state == JOINING_CONFIG_CHANGED):
            return safe_plugin(self._plugin.on_new_cluster_config_ready,
                               cluster_view,
                               new_state=NORMAL)

        # States for leaving a cluster

        elif (cluster_state == LEAVE_PENDING and
                local_state == WAITING_TO_LEAVE):
            sleep(SyncFSM.DELAY)
            return self._switch_all_to_leaving(cluster_view)
        elif (cluster_state == LEAVE_PENDING and
                local_state == NORMAL):
            return None

        elif (cluster_state == STARTED_LEAVING and
                local_state == LEAVING_ACKNOWLEDGED_CHANGE):
            return None
        elif (cluster_state == STARTED_LEAVING and
                local_state == NORMAL_ACKNOWLEDGED_CHANGE):
            return None
        elif (cluster_state == STARTED_LEAVING and
                local_state == NORMAL):
            return NORMAL_ACKNOWLEDGED_CHANGE
        elif (cluster_state == STARTED_LEAVING and
                local_state == LEAVING):
            return LEAVING_ACKNOWLEDGED_CHANGE

        elif (cluster_state == LEAVING_CONFIG_CHANGING and
                local_state == NORMAL_CONFIG_CHANGED):
                return None
        elif (cluster_state == LEAVING_CONFIG_CHANGING and
                local_state == LEAVING_CONFIG_CHANGED):
                return None
        elif (cluster_state == LEAVING_CONFIG_CHANGING and
                local_state == NORMAL_ACKNOWLEDGED_CHANGE):
            return safe_plugin(self._plugin.on_cluster_changing,
                               cluster_view,
                               new_state=NORMAL_CONFIG_CHANGED)
        elif (cluster_state == LEAVING_CONFIG_CHANGING and
                local_state == LEAVING_ACKNOWLEDGED_CHANGE):
            return safe_plugin(self._plugin.on_cluster_changing,
                               cluster_view,
                               new_state=LEAVING_CONFIG_CHANGED)

        elif (cluster_state == LEAVING_RESYNCING and
                local_state == NORMAL):
            return None
        elif (cluster_state == LEAVING_RESYNCING and
                local_state == FINISHED):
            return None
        elif (cluster_state == LEAVING_RESYNCING and
                local_state == LEAVING_CONFIG_CHANGED):
            return safe_plugin(self._plugin.on_new_cluster_config_ready,
                               cluster_view,
                               new_state=FINISHED)
        elif (cluster_state == LEAVING_RESYNCING and
                local_state == NORMAL_CONFIG_CHANGED):
            return safe_plugin(self._plugin.on_new_cluster_config_ready,
                               cluster_view,
                               new_state=NORMAL)

        elif (cluster_state == FINISHED_LEAVING and
                local_state == NORMAL):
            return None
        elif (cluster_state == FINISHED_LEAVING and
                local_state == FINISHED):
            self._running = False
            return safe_plugin(self._plugin.on_leaving_cluster,
                               cluster_view,
                               new_state=self._delete_myself(cluster_view))

        # Any valid state should have caused me to return by now
        _log.error("Invalid state in state machine for {} - local state {}, "
                   "cluster state {} and cluster view {}".format(
                       self._id,
                       local_state,
                       cluster_state,
                       cluster_view))
        return None
