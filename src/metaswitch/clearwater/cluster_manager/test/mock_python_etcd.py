from threading import Condition
from etcd import EtcdResult

class MockEtcdClient(object):
    def __init__(self, _host, _port):
        self._allowed_key = '/test'
        self._data = {}
        self._index = 0
        self._condvar = Condition()

    def fake_result(self):
        r = EtcdResult(None, {})
        r.value = self._data
        r.createdIndex = 1
        r.modifiedIndex = self._index
        return r

    def get(self, key):
        assert(key == self._allowed_key)
        if self._index == 0:
            raise etcd.KeyError()
        return self.fake_result()

    def write(self, key, value, prevIndex=0, prevExist=None):
        assert(key == self._allowed_key)
        if (prevIndex != self._index) and (prevIndex != 0):
            raise ValueError()
        if prevExist and self._index != 0:
            raise ValueError()
        self._condvar.acquire()
        self._data = value
        self._index += 1
        self._condvar.notify_all()
        self._condvar.release()
        return self.fake_result()

    def watch(self, key, index=None, timeout=None):
        assert(key == self._allowed_key)
        self._condvar.acquire()
        if index > self._index:
            self._condvar.wait(timeout)
        self._condvar.release()
        return self.fake_result()

    def eternal_watch(self, key, index=None):
        return self.watch(key, index, 36000)
