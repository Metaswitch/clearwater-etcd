from threading import Condition
import etcd
from etcd import EtcdResult, Client
from random import random
from time import sleep
import urllib3
import os

allowed_key = '/test'
global_data = ""
global_index = 0
global_condvar = Condition()

def EtcdFactory(*args, **kwargs):
    if os.environ.get('ETCD_IP'):
        return Client(os.environ.get('ETCD_IP'),
                      os.environ.get('ETCD_PORT', 4001))
    else:
        return MockEtcdClient(None, None)

class MockEtcdClient(object):
    def __init__(self, _host, _port):
        pass

    @classmethod
    def clear(self):
        global global_index
        global global_data
        global_condvar.acquire()
        global_index = 0
        global_data = ""
        global_condvar.release()

    def fake_result(self):
        r = EtcdResult(None, {})
        r.value = global_data
        r.createdIndex = 1
        r.modifiedIndex = global_index
        return r

    def get(self, key):
        global_condvar.acquire()
        assert(key == allowed_key)
        if global_index == 0:
            global_condvar.release()
            raise etcd.EtcdKeyError()
        ret = self.fake_result()
        global_condvar.release()
        return ret

    def write(self, key, value, prevIndex=0, prevExist=None):
        global global_index
        global global_data
        assert(key == allowed_key)
        global_condvar.acquire()
        if (((prevIndex != global_index) and (prevIndex != 0)) or
                (prevExist and global_index != 0)):
            global_condvar.release()
            raise ValueError()
        global_data = value
        global_index += 1
        global_condvar.notify_all()
        global_condvar.release()
        return self.fake_result()

    def watch(self, key, index=None, timeout=None, recursive=None):
        assert(key == allowed_key)
        global_condvar.acquire()
        if index > global_index:
            global_condvar.wait(0.1)
        if index > global_index:
            global_condvar.release()
            raise urllib3.exceptions.TimeoutError
        ret = self.fake_result()
        global_condvar.release()
        return ret

    def eternal_watch(self, key, index=None):
        return self.watch(key, index, 36000)


class SlowMockEtcdClient(MockEtcdClient):
    def write(self, key, value, prevIndex=0, prevExist=None):
        """Make writes take 0-200ms to discover race conditions"""
        sleep(random()/5.0)
        super(SlowMockEtcdClient, self).write(key, value, prevIndex=prevIndex, prevExist=prevExist)
