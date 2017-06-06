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
    install_requires=[
        "docopt==0.6.2",
        "futures==3.0.5",
        "prctl==1.0.1",
        "python-etcd==0.4.3",
        "py2_ipaddress==3.4.1",
        "pyyaml==3.11",
        "six==1.10.0",
        "urllib3==1.21.1"],
    tests_require=[
        "funcsigs==1.0.2",
        "Mock==2.0.0",
        "pbr==1.6",
        "six==1.10.0"],
    )
