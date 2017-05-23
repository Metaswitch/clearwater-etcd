# @file setup.py
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
    name='clearwater-config-manager',
    version='1.0',
    namespace_packages = ['metaswitch'],
    packages=['metaswitch', 'metaswitch.clearwater', 'metaswitch.clearwater.config_manager'],
    package_dir={'':'src'},
    package_data={
        '': ['*.eml'],
        },
    test_suite='metaswitch.clearwater.config_manager.test',
    install_requires=["docopt", "pyzmq==16.0.2", "urllib3==1.17", "python-etcd==0.4.3", "pyyaml==3.11", "prctl", "metaswitchcommon", "clearwater_etcd_shared"],
    tests_require=["pbr==1.6", "Mock"],
    )
