

import unittest
import subprocess
import os
import mock

import metaswitch.clearwater.config_manager.config_type_plugin_loader as config_type_plugin_loader
import metaswitch.clearwater.config_manager.config_type_class_plugin as config_type_class_plugin
from clearwater_etcd_plugins.clearwater_config_access import dns_json_config_plugin
from clearwater_etcd_plugins.clearwater_config_access import shared_config_config_plugin
from clearwater_etcd_plugins.clearwater_config_access import shared_ifcs_config_plugin
from clearwater_etcd_plugins.clearwater_config_access import bgcf_json_config_plugin
from clearwater_etcd_plugins.clearwater_config_access import weatherwax_config_plugin


@mock.patch("metaswitch.clearwater.config_manager.config_type_class_plugin.log")
@mock.patch("metaswitch.clearwater.config_manager.config_type_class_plugin.subprocess.check_output")
class TestConfigTypeClassPlugin(unittest.TestCase):

    def test_validate_passes(self, mock_subprocess, mock_log):
        """uses script from DnsJson to ConfigType.validate and check log
         and subprocess called properly, check failed_scripts is empty
         at end of process"""
        dns_config = dns_json_config_plugin.DnsJson('path')
        answer = dns_config.validate()

        self.assertIs(mock_log.debug.call_count, 1)
        self.assertIs(mock_log.error.call_count, 0)
        self.assertListEqual(answer, [])
        self.assertIs(mock_subprocess.call_count, 1)

    def test_validate_fails(self, mock_subprocess, mock_log):
        """use ConfigType.validate and get subprocess to raise a exception and
         check log reports this and failed scripts is not empty"""
        shared_config = shared_config_config_plugin.SharedConfig('path')
        shared_config.scripts = ['script1', 'script2']
        mock_subprocess.side_effect = [None,
                                       subprocess.CalledProcessError("A", "B")]
        # possibly want to run this within assertRaises check as well
        answer = shared_config.validate()

        self.assertIs(mock_log.debug.call_count, 2)
        self.assertIs(mock_log.error.call_count, 1)
        self.assertListEqual(answer, ['script2'])
        self.assertIs(mock_subprocess.call_count, 2)

    @mock.patch("metaswitch.clearwater.config_manager.config_type_class_plugin.os")
    def test_init(self, mock_os, mock_subprocess, mock_log):
        """test ___init__ with filetype and check correct script finder
        picked """

        mock_os.return_value = ['script1', 'script2']

        bgcf_json = bgcf_json_config_plugin.BgcfJson('path')
        ifcs_xml = shared_ifcs_config_plugin.SharedIfcsXml('path')
        weatherwax = weatherwax_config_plugin.WeatherwaxConfig('path')
        shared_config = shared_config_config_plugin.SharedConfig('path')

        list1 = [['python', '/usr/share/clearwater/clearwater-config-manager/scripts/validate_json.py',
                  '/usr/share/clearwater/clearwater-config-manager/scripts/config_validation/bgcf_schema.json',
                  'path'], ]
        list2 = [['xmllint', '--format', '--pretty', '1', '--load-trace',
                  '--debug', '--schema',
                  '$/usr/share/clearwater/clearwater-config-manager/scripts/config_validation/shared_ifcs_schema.xsd',
                  '$path'], ]
        list3 = []
        list4 = ['script1', 'script2']

        self.assertListEqual(bgcf_json.scripts, list1)
        self.assertListEqual(ifcs_xml.scripts, list2)
        self.assertListEqual(weatherwax.scripts, list3)
        self.assertListEqual(shared_config.scripts, list4)


class TestConfigTypePluginLoader(unittest.TestCase):
    # maybe tests already to test this for the function as used elsewhere
    # as it is just the same
    def test_load(self):
        plugin_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   "plugins")
        plugins = config_type_plugin_loader.load_plugins_in_dir(plugin_path, None)
        # Check that the plugin loaded successfully
        self.assertEqual(plugins[0].__class__.__name__,
                         "PluginLoaderTestPlugin")
