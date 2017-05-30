# @file setup.py
#
# Copyright (C) Metaswitch Networks 2016
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
    name='clearwater-etcd-shared',
    version='1.0',
    packages=['metaswitch', 'metaswitch.clearwater', 'metaswitch.clearwater.etcd_shared'],
    package_dir={'':'src'},
    package_data={
        '': ['*.eml'],
        },
    # Note - if you are updating the version of python-etcd, check if you should
    # remove the monkeypatch in the common_etcd_synchronizer
    install_requires=["docopt", "urllib3==1.17", "python-etcd==0.4.3", "pyzmq==16.0.2", "pyyaml==3.11"],
    tests_require=["Mock"],
    )
