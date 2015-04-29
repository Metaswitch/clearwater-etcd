from time import sleep

class FakeEtcdSynchronizer(object):
  def __init__(self, plugin, ip):
    self._fsm = SyncFSM(plugin, ip)

  def main(self):
    cluster = {"10.0.0.1": "NORMAL", "10.0.0.2": "NORMAL"}
    while True:
      self._fsm.next("NORMAL", "stable", cluster)
      sleep(10)

class TooLongAlarm(object):
  def alarm(self):
    sleep(15 * 60)
    send_alarm

  def trigger(self):
    if self._timer_thread == None:
      self._timer_thread = Thread

  def cancel(self):
    # cancel the thread
    self._timer_thread = None
    # clear the alarm

class SyncFSM(object):
  def __init__(self, plugin, local_ip):
    self._plugin = plugin
    self._id = local_ip
    self._running = True

  def _switch_all_to_joining(self, cluster_view):
    return {k: ("JOINING" if v == "WAITING_TO_JOIN" else v)
            for k, v in cluster_view.iteritems()}

  def _switch_all_to_leaving(self, cluster_view):
    return {k: ("LEAVING" if v == "WAITING_TO_LEAVE" else v)
            for k, v in cluster_view.iteritems()}

  def _switch_myself_to(self, new_state, cluster_view):
    cluster_view.update({self._id: new_state})
    return cluster_view

  def _delete_myself(self, cluster_view):
      return {k: v for k, v in a.iteritems() if k != self._id}

  def next(self, local_state, cluster_state, cluster_view):
    assert(self._running)

    if cluster_state == "stable":
      if local_state == "NORMAL":
        # Cancel 15-minute timer
        self._plugin.on_stable_cluster(cluster_view)
        return None
      elif local_state is None:
        return self._switch_myself_to("WAITING_TO_JOIN", cluster_view)

    # States for joining a cluster
    
    elif cluster_state == "join_pending":
      if local_state == "WAITING_TO_JOIN":
        sleep(30)
        return self._switch_all_to_joining(cluster_view)
      elif local_state == "NORMAL":
        return None
      elif local_state is None:
        return self._switch_myself_to("WAITING_TO_JOIN", cluster_view)
    
    
    elif cluster_state == "started_joining":
      if local_state in ["JOINING_ACKNOWLEDGED_CHANGE", "NORMAL_ACKNOWLEDGED_CHANGE"]:
        return None
      elif local_state == "NORMAL":
        # Start 15-minute timer
        return self._switch_myself_to("NORMAL_ACKNOWLEDGED_CHANGE", cluster_view)
      elif local_state == "JOINING":
        # Start 15-minute timer
        self._plugin.on_joining_cluster(cluster_view)
        return self._switch_myself_to("JOINING_ACKNOWLEDGED_CHANGE", cluster_view)
    
    
    elif cluster_state == "joining_config_changing":
      if local_state in ["JOINING_CONFIG_CHANGED", "NORMAL_CONFIG_CHANGED"]:
        return None
      elif local_state == "NORMAL_ACKNOWLEDGED_CHANGE":
        self._plugin.on_new_members(cluster_view)
        return self._switch_myself_to("NORMAL_CONFIG_CHANGED", cluster_view)
      elif local_state == "JOINING_ACKNOWLEDGED_CHANGE":
        self._plugin.on_new_members(cluster_view)
        return self._switch_myself_to("JOINING_CONFIG_CHANGED", cluster_view)
    
    
    elif cluster_state == "joining_resyncing":
      if local_state == "NORMAL":
        return None
      elif local_state == "JOINING_CONFIG_CHANGED":
        self._plugin.on_all_config_updated(cluster_view)
        return self._switch_myself_to("NORMAL", cluster_view)
      elif local_state == "NORMAL_CONFIG_CHANGED":
        self._plugin.on_all_config_updated(cluster_view)
        return self._switch_myself_to("NORMAL", cluster_view)

    # States for leaving a cluster

    elif cluster_state == "leave_pending":
      if local_state == "WAITING_TO_LEAVE":
        sleep(30)
        return switch_all_to_leaving(cluster_view)
      elif local_state == "NORMAL":
        return None
    
    
    elif cluster_state == "started_leaving":
      if local_state in ["LEAVING_ACKNOWLEDGED_CHANGE", "NORMAL_ACKNOWLEDGED_CHANGE"]:
        return None
      elif local_state == "NORMAL":
        # Start 15-minute timer
        return self._switch_myself_to("NORMAL_ACKNOWLEDGED_CHANGE", cluster_view)
      elif local_state == "LEAVING":
        # Start 15-minute timer
        return self._switch_myself_to("LEAVING_ACKNOWLEDGED_CHANGE", cluster_view)
    
    
    elif cluster_state == "leaving_config_changing":
      if local_state in ["LEAVING_CONFIG_CHANGED", "NORMAL_CONFIG_CHANGED"]:
        return None
      elif local_state == "NORMAL_ACKNOWLEDGED_CHANGE":
        self._plugin.on_new_members(cluster_view)
        return self._switch_myself_to("NORMAL_CONFIG_CHANGED", cluster_view)
      elif local_state == "LEAVING_ACKNOWLEDGED_CHANGE":
        self._plugin.on_new_members(cluster_view)
        return self._switch_myself_to("LEAVING_CONFIG_CHANGED", cluster_view)
    
    
    elif cluster_state == "leaving_resyncing":
      if local_state == "NORMAL":
        return None
      elif local_state == "JOINING_CONFIG_CHANGED":
        self._plugin.on_all_config_updated(cluster_view)
        return self._switch_myself_to("NORMAL", cluster_view)
      elif local_state == "NORMAL_CONFIG_CHANGED":
        self._plugin.on_all_config_updated(cluster_view)
        return self._switch_myself_to("NORMAL", cluster_view)
 
    elif cluster_state == "finished_leaving":
      if local_state == "NORMAL":
        return None
      if local_state == "FINISHED":
        self._plugin.on_left_cluster(cluster_view)
        self._running = False
        return self._delete_myself(cluster_view)

    # Any valid state should have caused me to return by now

def test():
  plg = DummyPlugin()
  fsm = SyncFSM(plg, "10.0.0.2")
  cluster = {"10.0.0.1": "NORMAL", "10.0.0.2": "WAITING_TO_JOIN"}
  print fsm.next("WAITING_TO_JOIN", "join_pending", cluster)

