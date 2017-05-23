# @file plugins_setup.py
#
# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import logging
import sys
import multiprocessing

from setuptools import setup, find_packages

setup(
    name='clearwater-etcd-plugin-tests',
    version='1.0',
    namespace_packages = ['metaswitch'],
    packages=['metaswitch', 'metaswitch.clearwater', 'metaswitch.clearwater.plugin_tests','clearwater_etcd_plugins','clearwater_etcd_plugins.chronos', 'clearwater_etcd_plugins.clearwater_memcached', 'clearwater_etcd_plugins.clearwater_config_manager', 'clearwater_etcd_plugins.clearwater_queue_manager', 'clearwater_etcd_plugins.clearwater_cassandra'],
    package_dir={'':'src'},  
    package_data={
        '': ['*.eml'],
        },
    test_suite='metaswitch.clearwater.plugin_tests',
    tests_require=["pyzmq==16.0.2", "metaswitchcommon", "py2-ipaddress==3.4.1", "pbr==1.6", "Mock", "pyyaml==3.11"],
    )
