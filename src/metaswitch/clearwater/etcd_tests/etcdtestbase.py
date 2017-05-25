# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import unittest
from .etcdcluster import EtcdCluster
from metaswitch.common.logging_config import configure_test_logging

configure_test_logging()


class EtcdTestBase(unittest.TestCase):
    def test_basic_clustering(self):
        c = EtcdCluster(2)
        s1, s2 = c.servers.values()

        hasOneLeader = s1.isLeader() != s2.isLeader()

        self.assertTrue(hasOneLeader)
        self.assertTrue(s1.memberList() == s2.memberList())
        self.assertEquals(2, len(s1.memberList()))
        c.delete_datadir()

    def test_large_clusters(self):
        c = EtcdCluster(10)
        self.assertEquals(10, len(c.servers.values()[0].memberList()))
        c.delete_datadir()
