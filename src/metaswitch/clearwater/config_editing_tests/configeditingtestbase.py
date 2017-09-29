# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.
import sys
import unittest
from metaswitch.common.logging_config import configure_test_logging
__import__("cw-config")

# sys.modules["etcd"] = fakemodule

configure_test_logging()

class ConfigEditingTestBase(unittest.TestCase):
    def test_nothing(self):
        pass

