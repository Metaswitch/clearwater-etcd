#!/usr/bin/env python

import unittest
from metaswitch.clearwater.cluster_manager.plugin_loader \
    import load_plugins_in_dir
import os


class TestPluginLoading(unittest.TestCase):

    def test_load(self):
        plugin_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   "plugins")
        plugins = load_plugins_in_dir(plugin_path, None)

        # Check that the plugin loaded successfully
        self.assertEqual(plugins[0].__class__.__name__,
                         "PluginLoaderTestPlugin")
