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
    name='clearwater-etcd-tests',
    version='1.0',
    test_suite='metaswitch.clearwater.etcd_tests',
    tests_require=["urllib3==1.17", "python-etcd"],
    )
