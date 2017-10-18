

import unittest
import subprocess
import os
import mock

import metaswitch.clearwater.config_manager.config_type_plugin_loader as config_type_plugin_loader
from clearwater_etcd_plugins.clearwater_config_access import dns_json_config_plugin
from clearwater_etcd_plugins.clearwater_config_access import shared_config_config_plugin
from clearwater_etcd_plugins.clearwater_config_access import shared_ifcs_config_plugin
from clearwater_etcd_plugins.clearwater_config_access import bgcf_json_config_plugin
from clearwater_etcd_plugins.clearwater_config_access import weatherwax_config_plugin
from clearwater_etcd_plugins.clearwater_config_access import scscf_json_config_plugin
from clearwater_etcd_plugins.clearwater_config_access import fallback_ifcs_config_plugin


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
        weatherwax_config = weatherwax_config_plugin.WeatherwaxConfig('path')
        weatherwax_config.scripts = ['script1', 'script2']
        mock_subprocess.side_effect = [None,
                                       subprocess.CalledProcessError("A", "B")]
        # possibly want to run this within assertRaises check as well
        answer = weatherwax_config.validate()

        self.assertIs(mock_log.debug.call_count, 2)
        self.assertIs(mock_log.error.call_count, 1)
        self.assertListEqual(answer, ['script2'])
        self.assertIs(mock_subprocess.call_count, 2)

    @mock.patch("metaswitch.clearwater.config_manager.config_type_class_plugin.ConfigType.get_json_validation")
    @mock.patch("metaswitch.clearwater.config_manager.config_type_class_plugin.ConfigType.get_xml_validation")
    @mock.patch("metaswitch.clearwater.config_manager.config_type_class_plugin.ConfigType.get_sharedconfig_validation")
    def test_init(self, mock_shared, mock_xml, mock_json, mock_subprocess, mock_log):
        """test ___init__ with filetype and check correct script finder
        picked """

        mock_json.return_value = ['script1', 'script2']
        mock_xml.return_value = ['script3', 'script4']
        mock_shared.return_value = ['script5', 'script6']

        bgcf_json = bgcf_json_config_plugin.BgcfJson('path')
        ifcs_xml = shared_ifcs_config_plugin.SharedIfcsXml('path')
        weatherwax = weatherwax_config_plugin.WeatherwaxConfig('path')
        shared_config = shared_config_config_plugin.SharedConfig('path')
        print shared_config.scripts

        list1 = ['script1', 'script2']
        list2 = ['script3', 'script4']
        list3 = []
        list4 = ['script5', 'script6']

        self.assertListEqual(bgcf_json.scripts, list1)
        self.assertListEqual(ifcs_xml.scripts, list2)
        self.assertListEqual(weatherwax.scripts, list3)
        self.assertListEqual(shared_config.scripts, list4)


class TestGetValidationScripts(unittest.TestCase):
    def test_get_json(self):
        """tests the get_json_validation returns the correct list of scripts
        where each script is a list"""
        # currently only one
        scscf_json = scscf_json_config_plugin.ScscfJson('path')
        answer = scscf_json.get_json_validation()
        list1 = [['python',
                  '/usr/share/clearwater/clearwater-config-manager/scripts/validate_json.py',
                  '/usr/share/clearwater/clearwater-config-manager/scripts/config_validation/scscf_schema.json',
                  'path']]
        self.assertListEqual(answer, list1)

    def test_get_xml(self):
        """tests the get_xml_validation returns the correct list of scripts
        where each script is a list"""
        # currently only one
        fallback_ifcs = fallback_ifcs_config_plugin.FallbackIfcsXml('path')
        answer = fallback_ifcs.get_xml_validation()
        list2 = [['xmllint', '--format', '--pretty', '1', '--load-trace',
                  '--debug', '--schema',
                  '$/usr/share/clearwater/clearwater-config-manager/scripts/config_validation/fallback_ifcs_schema.xsd',
                  '$path', ]]
        self.assertListEqual(answer, list2)

    @mock.patch("metaswitch.clearwater.config_manager.config_type_class_plugin.os")
    def test_get_shared(self, mock_os):
        """tests the get_sharedconfig_validation script calls the
        os function"""
        shared_config_config_plugin.SharedConfig('path')
        self.assertIs(mock_os.listdir.call_count, 1)


class TestConfigTypePluginLoader(unittest.TestCase):
    # uses the test for the plugin loader already created
    def test_load(self):
        """tests the plugin loader loads plug ins"""
        plugin_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   "plugins")
        plugins = config_type_plugin_loader.load_plugins_in_dir(plugin_path, None)
        # Check that the plugin loaded successfully
        self.assertEqual(plugins[0].__class__.__name__,
                         "PluginLoaderTestPlugin")
