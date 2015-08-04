# Project Clearwater - IMS in the Cloud
# Copyright (C) 2015 Metaswitch Networks Ltd
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version, along with the "Special Exception" for use of
# the program along with SSL, set forth below. This program is distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details. You should have received a copy of the GNU General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
# The author can be reached by email at clearwater@metaswitch.com or by
# post at Metaswitch Networks Ltd, 100 Church St, Enfield EN2 6BQ, UK
#
# Special Exception
# Metaswitch Networks Ltd  grants you permission to copy, modify,
# propagate, and distribute a work formed by combining OpenSSL with The
# Software, or a work derivative of such a combination, even if such
# copying, modification, propagation, or distribution would otherwise
# violate the terms of the GPL. You must comply with the GPL in all
# respects for all of the code used other than OpenSSL.
# "OpenSSL" means OpenSSL toolkit software distributed by the OpenSSL
# Project and licensed under the OpenSSL Licenses, or a work based on such
# software and licensed under the OpenSSL Licenses.
# "OpenSSL Licenses" means the OpenSSL License and Original SSLeay License
# under which the OpenSSL Project distributes the OpenSSL toolkit software,
# as those licenses appear in the file LICENSE-OPENSSL.

from threading import Condition
import etcd
from etcd import EtcdResult, Client
from random import random, choice
from time import sleep
import urllib3
import os

allowed_key = '/test'
global_data = "INVALID_JSON"
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

    def fake_result(self):
        r = EtcdResult(None, {})
        r.value = global_data
        r.createdIndex = 1
        r.modifiedIndex = global_index
        return r

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

    def read(self, key, index=None, timeout=None, recursive=None, **kwargs):
        assert(key == allowed_key)
        global_condvar.acquire()
        if global_index == 0:
            global_condvar.release()
            raise etcd.EtcdKeyError()
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
        super(SlowMockEtcdClient, self).write(key,
                                              value,
                                              prevIndex=prevIndex,
                                              prevExist=prevExist)


class ExceptionMockEtcdClient(MockEtcdClient):
    def write(self, key, value, prevIndex=0, prevExist=None):
        if random() > 0.9:
            e = choice([etcd.EtcdException, etcd.EtcdKeyError])
            raise e
        return super(ExceptionMockEtcdClient, self).write(key,
                                                          value,
                                                          prevIndex=prevIndex,
                                                          prevExist=prevExist)

    def watch(self, key, index=None, timeout=None, recursive=None):
        if random() > 0.9:
            e = choice([etcd.EtcdException, ValueError])
            raise e
        return super(ExceptionMockEtcdClient, self).watch(key,
                                                          index=index,
                                                          timeout=timeout,
                                                          recursive=recursive)
