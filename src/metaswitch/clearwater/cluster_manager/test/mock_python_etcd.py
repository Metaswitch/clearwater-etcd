from threading import Condition
import etcd
from etcd import EtcdResult

allowed_key = '/test'
global_data = "{}"
global_index = 0
global_condvar = Condition()

class MockEtcdClient(object):
    def __init__(self, _host, _port):
        pass

    def fake_result(self):
        r = EtcdResult(None, {})
        r.value = global_data
        r.createdIndex = 1
        r.modifiedIndex = global_index
        return r

    def get(self, key):
        assert(key == allowed_key)
        if global_index == 0:
            raise etcd.EtcdKeyError()
        return self.fake_result()

    def write(self, key, value, prevIndex=0, prevExist=None):
        global global_index
        global global_data
        assert(key == allowed_key)
        if (prevIndex != global_index) and (prevIndex != 0):
            raise ValueError()
        if prevExist and global_index != 0:
            raise ValueError()
        global_condvar.acquire()
        print "%s successfully written" % value
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
        global_condvar.release()
        return self.fake_result()

    def eternal_watch(self, key, index=None):
        return self.watch(key, index, 36000)
