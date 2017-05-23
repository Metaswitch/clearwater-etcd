# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.
from metaswitch.clearwater.queue_manager.plugin_base import QueuePluginBase
from metaswitch.clearwater.queue_manager.etcd_synchronizer import WriteToEtcdStatus

class TestPlugin(QueuePluginBase):
    def key(self):
        return "queue_test"

    def at_front_of_queue(self):
        pass

class TestFrontOfQueueCallbackPlugin(QueuePluginBase):
    def __init__(self):
        self._at_front_of_queue_called = False

    def key(self):
        return "queue_test"

    def at_front_of_queue(self):
        self._at_front_of_queue_called = True

class TestNoTimerDelayPlugin(QueuePluginBase):
    def __init__(self):
        self.WAIT_FOR_OTHER_NODE = 0
        self.WAIT_FOR_THIS_NODE = 0

    def key(self):
        return "queue_test"

    def at_front_of_queue(self):
        pass

class TestFVPlugin(QueuePluginBase):
    def __init__(self, *args, **kwargs):
        super(TestFVPlugin, self).__init__(*args, **kwargs)
        self.at_front_of_queue_called = False
        self.front_of_queue_callback = None

    def key(self):
        return "queue_test"

    def when_at_front_of_queue(self, cb):
        self.front_of_queue_callback = cb

    def at_front_of_queue(self):
        self.at_front_of_queue_called = True
        rc = self.front_of_queue_callback()
        while rc != WriteToEtcdStatus.SUCCESS:
            rc = self.front_of_queue_callback()
