# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

from threading import Condition
import consul
from consul import Timeout, Consul
from random import random
from time import sleep
import os

allowed_key = 'test'
global_data = None
global_index = 0
global_condvar = Condition()


def ConsulFactory(*args, **kwargs):
    """Factory method, returning a connection to a real etcd if we need one for
    FV, or to an in-memory implementation for UT."""
    if os.environ.get('ETCD_IP'):
        return Consul(host=os.environ.get('ETCD_IP'),
                      port=int(os.environ.get('ETCD_PORT', 8500)))
    else:
        return MockConsulClient(None, None)


class MockConsulClient(object):
    def __init__(
            self,
            host='127.0.0.1',
            port=8500,
            token=None,
            scheme='http',
            consistency='default',
            dc=None,
            verify=True,
            cert=None):
        self.kv = MockConsulKv()

    @classmethod
    def clear(self):
        MockConsulKv.clear()

class MockConsulKv(object):
    def __init__(self):
        self._value = None

    @classmethod
    def clear(self):
        global global_index
        global global_data
        global_condvar.acquire()
        global_index = 0
        global_data = None
        global_condvar.release()

    def fake_result(self, key):
        return (global_index, {
                "CreateIndex": 1,
                "ModifyIndex": global_index,
                "LockIndex": 1,
                "Key": key,
                "Flags": 0,
                "Value": global_data,
                "Session": "adf4238a-882b-9ddc-4a9d-5b6758e4159e"
            })

    def get(
            self,
            key,
            index=None,
            recurse=False,
            wait=None,
            token=None,
            consistency=None,
            keys=False,
            separator=None,
            dc=None):

        with global_condvar:
            if wait:
                if global_index == 0:
                    return (global_index, None)
                if index > global_index:
                    global_condvar.wait(0.1)
                if index > global_index:
                    raise Timeout
            if global_data == None:
                return (global_index, None)
            ret = self.fake_result(key)
        return ret

    def put(
            self,
            key,
            value,
            cas=None,
            flags=None,
            acquire=None,
            release=None,
            token=None,
            dc=None):

        global global_index
        global global_data
        global_condvar.acquire()
        if (cas != None) and (cas != global_index):
            global_condvar.release()
            return False
        global_data = value
        global_index += 1
        global_condvar.notify_all()
        global_condvar.release()

        return True

    def get_noexcept(self, *args, **kwargs):
        """Method to allow the UT infrastructure to read the value, without
        triggering an exception."""
        return self.get(*args, **kwargs)

class SlowMockConsulClient(MockConsulClient):
    def __init__(
            self,
            host='127.0.0.1',
            port=8500,
            token=None,
            scheme='http',
            consistency='default',
            dc=None,
            verify=True,
            cert=None):
        self.kv = SlowMockConsulKv()


class SlowMockConsulKv(MockConsulKv):
    def put(
            self,
            key,
            value,
            cas=None,
            flags=None,
            acquire=None,
            release=None,
            token=None,
            dc=None):
        """Make writes take 0-200ms to discover race conditions"""
        sleep(random()/5.0)
        super(SlowMockConsulKv, self).write(key,
                                            value,
                                            cas=cas,
                                            flags=flags,
                                            acquire=acquire,
                                            release=release,
                                            token=token,
                                            dc=dc)

    def get_noexcept(self, *args, **kwargs):
        """Method to allow the UT infrastructure to read the value, without
        triggering an exception."""
        return super(SlowMockConsulKv, self).get(*args, **kwargs)


class ExceptionMockConsulClient(MockConsulClient):
    def __init__(
            self,
            host='127.0.0.1',
            port=8500,
            token=None,
            scheme='http',
            consistency='default',
            dc=None,
            verify=True,
            cert=None):
        self.kv = ExceptionMockConsulKv()


class ExceptionMockConsulKv(MockConsulKv):
    def get(self, *args, **kwargs):
        if random() > 0.9:
            raise consul.ConsulException("sample message")
        return super(ExceptionMockConsulKv, self).get(*args, **kwargs)

    def put(self, *args, **kwargs):
        if random() > 0.9:
            raise consul.ConsulException("sample message")
        return super(ExceptionMockConsulKv, self).put(*args, **kwargs)

    def get_noexcept(self, *args, **kwargs):
        """Method to allow the UT infrastructure to read the value, without
        triggering an exception."""
        return super(ExceptionMockConsulKv, self).get(*args, **kwargs)
