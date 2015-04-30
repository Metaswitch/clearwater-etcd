from threading import Condition
from etcd import EtcdResult

class MockEtcdClient(object):
    def __init__(self):
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
        return self._data

    def set(self, key, value):
        assert(key == self._allowed_key)
        self._condvar.acquire()
        self._data = value
        self._index += 1
        self._condvar.notify_all()
        self._condvar.release()

    def watch(self, key, index=None, timeout=None, recursive=None):
        self._condvar.acquire()
        while index < self._index:
            self._condvar.wait(timeout)
        self._condvar.release()
        return self._data
