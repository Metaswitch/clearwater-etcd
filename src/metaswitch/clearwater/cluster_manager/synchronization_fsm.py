from time import sleep
from .constants import *
from .alarms import TooLongAlarm
import etcd
import logging

_log = logging.getLogger("cluster_manager.fsm")

class FakeEtcdSynchronizer(object):
    def __init__(self, plugin, ip):
        self._fsm = SyncFSM(plugin, ip)
        self.client = etcd.Client(None, None)

    def main(self):
        cluster = {"10.0.0.1": "normal", "10.0.0.2": "normal"}
        while True:
            self._fsm.next("normal", STABLE, cluster)
            sleep(10)


class SyncFSM(object):
    DELAY = 30

    def __init__(self, plugin, local_ip):
        self._plugin = plugin
        self._id = local_ip
        self._running = True
        self._alarm = TooLongAlarm()

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
        return {k: v for k, v in a.iteritems() if k != self._id}

    def next(self, local_state, cluster_state, cluster_view):
        print("Entered state mchine for {} with local state {}, "
                   "cluster state {} and cluster view {}".format(
                   self._id,
                   local_state,
                   cluster_state,
                   cluster_view))
        assert(self._running)
        if local_state == NORMAL:
            self._alarm.cancel()
        else:
            self._alarm.trigger()

        if cluster_state == STABLE:
            if local_state == NORMAL:
                try:
                    self._plugin.on_stable_cluster(cluster_view)
                except Exception as e:
                    _log.error("Call to on_stable_cluster method of {} "
                               "with cluster {} caused exception {}".format(
                               self._plugin,
                               cluster_view,
                               e))
                return None
            elif local_state is None:
                return self._switch_myself_to(WAITING_TO_JOIN, cluster_view)

        # States for joining a cluster

        elif cluster_state == JOIN_PENDING:
            if local_state == WAITING_TO_JOIN:
                sleep(SyncFSM.DELAY)
                return self._switch_all_to_joining(cluster_view)
            elif local_state == NORMAL:
                return None
            elif local_state is None:
                return self._switch_myself_to(WAITING_TO_JOIN, cluster_view)

        elif cluster_state == STARTED_JOINING:
            if local_state in [JOINING_ACKNOWLEDGED_CHANGE, NORMAL_ACKNOWLEDGED_CHANGE]:
                return None
            elif local_state == NORMAL:
                return self._switch_myself_to(NORMAL_ACKNOWLEDGED_CHANGE, cluster_view)
            elif local_state == JOINING:
                self._plugin.on_joining_cluster(cluster_view)
                return self._switch_myself_to(JOINING_ACKNOWLEDGED_CHANGE, cluster_view)

        elif cluster_state == JOINING_CONFIG_CHANGING:
            if local_state in [JOINING_CONFIG_CHANGED, NORMAL_CONFIG_CHANGED]:
                return None
            elif local_state == NORMAL_ACKNOWLEDGED_CHANGE:
                try:
                    self._plugin.on_cluster_changing(cluster_view)
                    return self._switch_myself_to(NORMAL_CONFIG_CHANGED, cluster_view)
                except Exception as e:
                    _log.error("Call to on_cluster_changing method of {} "
                               "with cluster {} caused exception {}".format(
                               self._plugin,
                               cluster_view,
                               e))
                    return None
            elif local_state == JOINING_ACKNOWLEDGED_CHANGE:
                try:
                    self._plugin.on_cluster_changing(cluster_view)
                    return self._switch_myself_to(JOINING_CONFIG_CHANGED, cluster_view)
                except Exception as e:
                    _log.error("Call to on_cluster_changing method of {} "
                               "with cluster {} caused exception {}".format(
                               self._plugin,
                               cluster_view,
                               e))
                    return None

        elif cluster_state == JOINING_RESYNCING:
            if local_state == NORMAL:
                return None
            elif local_state in [JOINING_CONFIG_CHANGED, NORMAL_CONFIG_CHANGED]:
                try:
                    self._plugin.on_new_cluster_config_ready(cluster_view)
                    return self._switch_myself_to(NORMAL, cluster_view)
                except Exception as e:
                    _log.error("Call to on_new_cluster_config_ready method of {} "
                               "with cluster {} caused exception {}".format(
                               self._plugin,
                               cluster_view,
                               e))
                    return None

        # States for leaving a cluster

        elif cluster_state == LEAVE_PENDING:
            if local_state == WAITING_TO_LEAVE:
                sleep(SyncFSM.DELAY)
                return switch_all_to_leaving(cluster_view)
            elif local_state == NORMAL:
                return None

        elif cluster_state == STARTED_LEAVING:
            if local_state in [LEAVING_ACKNOWLEDGED_CHANGE, NORMAL_ACKNOWLEDGED_CHANGE]:
                return None
            elif local_state == NORMAL:
                return self._switch_myself_to(NORMAL_ACKNOWLEDGED_CHANGE, cluster_view)
            elif local_state == LEAVING:
                return self._switch_myself_to(LEAVING_ACKNOWLEDGED_CHANGE, cluster_view)

        elif cluster_state == LEAVING_CONFIG_CHANGING:
            if local_state in [LEAVING_CONFIG_CHANGED, NORMAL_CONFIG_CHANGED]:
                return None
            elif local_state == NORMAL_ACKNOWLEDGED_CHANGE:
                try:
                    self._plugin.on_cluster_changing(cluster_view)
                    return self._switch_myself_to(NORMAL_CONFIG_CHANGED, cluster_view)
                except Exception as e:
                    _log.error("Call to on_cluster_changing method of {} "
                               "with cluster {} caused exception {}".format(
                               self._plugin,
                               cluster_view,
                               e))
                    return None
            elif local_state == LEAVING_ACKNOWLEDGED_CHANGE:
                try:
                    self._plugin.on_cluster_changing(cluster_view)
                    return self._switch_myself_to(LEAVING_CONFIG_CHANGED, cluster_view)
                except Exception as e:
                    _log.error("Call to on_cluster_changing method of {} "
                               "with cluster {} caused exception {}".format(
                               self._plugin,
                               cluster_view,
                               e))
                    return None

        elif cluster_state == LEAVING_RESYNCING:
            if local_state == NORMAL:
                return None
            elif local_state == LEAVING_CONFIG_CHANGED:
                try:
                    self._plugin.on_new_cluster_config_ready(cluster_view)
                    return self._switch_myself_to(FINISHED, cluster_view)
                except Exception as e:
                    _log.error("Call to on_new_cluster_config_ready method of {} "
                               "with cluster {} caused exception {}".format(
                               self._plugin,
                               cluster_view,
                               e))
                    return None
            elif local_state == NORMAL_CONFIG_CHANGED:
                try:
                    self._plugin.on_new_cluster_config_ready(cluster_view)
                    return self._switch_myself_to(NORMAL, cluster_view)
                except Exception as e:
                    _log.error("Call to on_new_cluster_config_ready method of {} "
                               "with cluster {} caused exception {}".format(
                               self._plugin,
                               cluster_view,
                               e))
                    return None

        elif cluster_state == FINISHED_LEAVING:
            if local_state == NORMAL:
                return None
            if local_state == FINISHED:
                try:
                    self._plugin.on_leaving_cluster(cluster_view)
                    self._running = False
                    return self._delete_myself(cluster_view)
                except Exception as e:
                    _log.error("Call to on_leaving_cluster method of {} "
                               "with cluster {} caused exception {}".format(
                               self._plugin,
                               cluster_view,
                               e))
                    return None


        # Any valid state should have caused me to return by now
        _log.error("Invalid state in state machine for {} - local state {}, "
                    "cluster state {} and cluster view {}".format(
                    local_state,
                    cluster_state,
                    cluster_view))
        return None


def test():
    plg = DummyPlugin()
    fsm = SyncFSM(plg, "10.0.0.2")
    cluster = {"10.0.0.1": "normal", "10.0.0.2": "waiting to join"}
    print fsm.next("waiting to join", "join pending", cluster)
