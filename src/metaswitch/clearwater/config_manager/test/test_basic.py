#!/usr/bin/env python

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


import unittest
from metaswitch.clearwater.etcd_shared.test.mock_python_etcd import EtcdFactory
from metaswitch.clearwater.config_manager.etcd_synchronizer import \
    EtcdSynchronizer
from .plugin import TestPlugin
from mock import patch
from threading import Thread
from time import sleep


class BasicTest(unittest.TestCase):
    @patch("etcd.Client", new=EtcdFactory)
    def test_synchronisation(self):
        p = TestPlugin()
        e = EtcdSynchronizer(p, "10.0.0.1", "local", None, "clearwater")
        # Write some initial data into the key
        e._client.write("/clearwater/local/configuration/test", "initial data")

        thread = Thread(target=e.main_wrapper)
        thread.daemon=True
        thread.start()

        sleep(1)
        # Write a new value into etcd, and check that the plugin is called with
        # it
        e._client.write("/clearwater/local/configuration/test", "hello world")
        sleep(1)
        p._on_config_changed.assert_called_with("hello world", None)

        # Allow the EtcdSynchronizer to exit
        e._terminate_flag = True
        sleep(1)

    @patch("etcd.Client", new=EtcdFactory)
    def test_key_not_present(self):
        p = TestPlugin()
        e = EtcdSynchronizer(p, "10.0.0.1", "local", None, "clearwater")

        thread = Thread(target=e.main_wrapper)
        thread.daemon=True
        thread.start()

        sleep(1)
        p._on_config_changed.assert_called_with("default_value", None)

        # Allow the EtcdSynchronizer to exit
        e._terminate_flag = True
        sleep(1)

    @patch("etcd.Client", new=EtcdFactory)
    def test_non_ascii(self):
        p = TestPlugin()
        e = EtcdSynchronizer(p, "10.0.0.1", "local", None, "clearwater")
        # Write some initial data into the key
        e._client.write("/clearwater/local/configuration/test", "initial data")

        thread = Thread(target=e.main_wrapper)
        thread.daemon=True
        thread.start()

        sleep(1)
        # Write a new value into etcd, and check that the plugin is called with
        # it
        e._client.write("/clearwater/local/configuration/test", u'\x80non-ascii')
        sleep(1)
        p._on_config_changed.assert_called_with(u'\x80non-ascii', None)

        # Allow the EtcdSynchronizer to exit
        e._terminate_flag = True
        sleep(1)
