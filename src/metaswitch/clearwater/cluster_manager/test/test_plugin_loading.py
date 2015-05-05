#!/usr/bin/env python

import unittest
from metaswitch.clearwater.cluster_manager.plugin_loader import load_plugins_in_dir
import logging
import os

class TestPluginLoading(unittest.TestCase):

    def test_load(self):
        logging.getLogger().setLevel(logging.DEBUG)
        plugin_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "plugins")
        plugins = load_plugins_in_dir(plugin_path, 8)
        self.assertEqual(plugins[0].__class__.__name__, "PluginLoaderTestPlugin")
        logging.getLogger().setLevel(logging.ERROR)
