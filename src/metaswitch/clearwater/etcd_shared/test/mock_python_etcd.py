# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

from threading import Condition
import etcd
from etcd import EtcdResult, Client, EtcdException, EtcdKeyError
from random import random, choice
from time import sleep
import os

allowed_key = '/test'
global_data = ""
global_index = 0
global_condvar = Condition()


def EtcdFactory(*args, **kwargs):
    """Factory method, returning a connection to a real etcd if we need one for
    FV, or to an in-memory implementation for UT."""
    if os.environ.get('ETCD_IP'):
        return Client(os.environ.get('ETCD_IP'),
                      int(os.environ.get('ETCD_PORT', 4001)))
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

    def return_global_data(self):
        return global_data

    def fake_result(self):
        r = EtcdResult(None, {})
        r.value = global_data
        r.createdIndex = 1
        r.modifiedIndex = global_index
        r.etcd_index = global_index
        return r

    def write(self, key, value, prevIndex=0, prevExist=None):
        global global_index
        global global_data
        global_condvar.acquire()
        if (((prevIndex != global_index) and (prevIndex != 0)) or
                (prevExist and global_index != 0)):
            global_condvar.release()
            raise ValueError()
        global_data = value
        global_index += 1
        r = self.fake_result()
        global_condvar.notify_all()
        global_condvar.release()
        return r

    def read(self, key, wait=False, waitIndex=None, timeout=None, recursive=None, **kwargs):
        with global_condvar:
            if wait:
                if global_index == 0:
                    raise etcd.EtcdKeyError()
                if waitIndex > global_index:
                    global_condvar.wait(0.1)
                if waitIndex > global_index:
                    raise EtcdException("Read timed out")
            if global_data == "":
                raise EtcdKeyError("")
            ret = self.fake_result()
        return ret

    def read_noexcept(self, *args, **kwargs):
        return self.read(*args, **kwargs)


class SlowMockEtcdClient(MockEtcdClient):
    def write(self, key, value, prevIndex=0, prevExist=None):
        """Make writes take 0-200ms to discover race conditions"""
        sleep(random()/5.0)
        super(SlowMockEtcdClient, self).write(key,
                                              value,
                                              prevIndex=prevIndex,
                                              prevExist=prevExist)


class ExceptionMockEtcdClient(MockEtcdClient):
    def write(self, *args, **kwargs):
        if random() > 0.9:
            e = choice([etcd.EtcdException, etcd.EtcdKeyError])
            raise e("sample message")
        return super(ExceptionMockEtcdClient, self).write(*args, **kwargs)

    def read(self, *args, **kwargs):
        if random() > 0.9:
            e = choice([etcd.EtcdException, ValueError])
            raise e("sample message")
        return super(ExceptionMockEtcdClient, self).read(*args, **kwargs)

    def read_noexcept(self, *args, **kwargs):
        """Method to allow the UT infrastructure to read the value, without
        triggering an exception."""
        return super(ExceptionMockEtcdClient, self).read(*args, **kwargs)
