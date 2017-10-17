

import mock
import unittest
import subprocess
import os
import sys

import metaswitch.clearwater.config_manager.config_type_plugin_loader as config_type_plugin_loader
import metaswitch.clearwater.config_manager.config_type_class_plugin as config_type_class_plugin
from clearwater_etcd_plugins.clearwater_config_access import dns_json_config_plugin
from clearwater_etcd_plugins.clearwater_config_access import shared_config_config_plugin
from clearwater_etcd_plugins.clearwater_config_access import shared_ifcs_config_plugin
from clearwater_etcd_plugins.clearwater_config_access import bgcf_json_config_plugin
from clearwater_etcd_plugins.clearwater_config_access import weatherwax_config_plugin
import metaswitch.clearwater.config_manager.config_access as config_access


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


    def test_init(self, mock_subprocess, mock_log):
        """test ___init__ with filetype and check correct script finder
        picked """
        ifcs_xml = shared_ifcs_config_plugin.SharedIfcsXml('path')
        bgcf_json = bgcf_json_config_plugin.BgcfJson('path')
        weatherwax = weatherwax_config_plugin.WeatherwaxConfig('path')

        list1 = [['python', '/usr/share/clearwater/clearwater-config-manager/scripts/validate_json.py',
                  '/usr/share/clearwater/clearwater-config-manager/scripts/config_validation/bgcf_schema.json',
                  'path'], ]
        list2 = [['xmllint', '--format', '--pretty', '1', '--load-trace',
                  '--debug', '--schema',
                  '$/usr/share/clearwater/clearwater-config-manager/scripts/config_validation/shared_ifcs_schema.xsd',
                  '$path'], ]
        list3 = []

        self.assertListEqual(ifcs_xml.scripts, list2)
        self.assertListEqual(bgcf_json.scripts, list1)
        self.assertListEqual(weatherwax.scripts, list3)


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

# TODO
# these test config access so may be worth moving these tests into config_access
@mock.patch("metaswitch.clearwater.config_manager.config_access.load_plugins_in_dir")
class TestClassReturn(unittest.TestCase):

    def test_class_return(self, mock_loadplugins):
        """mock load_plugins_in_dir then create mock class structure?!?!
        then create dict and check with input the return is correct"""
        mock_loadplugins.side_effect = 'give list of fake classes'
        key = 'shared_config'
        answer = config_access.class_return(key)
        self.assertIs(class1, answer)


@mock.patch("metaswitch.clearwater.config_manager.config_access.load_plugins_in_dir")
class TestArguments(unittest.TestCase):
    def test_all_arguments(self, mock_loadplugins):
        """Test that every argument is set correctly."""
        sys.argv = ["config_access.py",
                    "--autoconfirm",
                    "--force",
                    "--log-dir", "some/dir",
                    "--log-level", "50",
                    "upload",
                    "shared_config",
                    "--management_ip", "1.2.3.4",
                    "--site", "siteX",
                    "--etcd_key", "lockpick"]

        args = config_access.parse_arguments()

        assert args.force
        assert args.autoconfirm
        assert args.log_dir == "some/dir"
        assert args.log_level == 50
        assert args.action == "upload"
        assert args.config_type == class1
        assert args.management_ip == "1.2.3.4"
        assert args.site == "siteX"
        assert args.etcd_key == "lockpick"

    def test_mandatory_args_only(self, mock_loadplugins):
        """Check that we correctly parse only the mandatory arguments."""
        sys.argv = ["config_access.py",
                    "download",
                    "shared_config",
                    "--management_ip", "1.2.3.4",
                    "--site", "siteX",
                    "--etcd_key", "lockpick"]

        args = config_access.parse_arguments()

        assert not args.force
        assert not args.autoconfirm
        assert args.log_level == logging.INFO
        assert args.action == "download"
        assert args.config_type == class1
        assert args.management_ip == "1.2.3.4"
        assert args.site == "siteX"
        assert args.etcd_key == "lockpick"

    def test_missing_args(self, mock_loadplugins):
        """Check that when the arguments are invalid we error out."""
        sys.argv = ["config_access.py",
                    "reload",
                    "shard_config"]

        # There's a config error, so we should fail.
        with self.assertRaises(SystemExit):
            config_access.parse_arguments()

    def test_wrong_config(self, mock_loadplugins):
        """check that when a config_type not in the choice list is provided
        a error is raised"""

        sys.argv = ["config_access.py",
                    "download",
                    "bgcf_json",
                    "--management_ip", "1.2.3.4",
                    "--site", "siteX",
                    "--etcd_key", "lockpick"]

        with self.assertRaises(SystemExit):
            config_access.parse_arguments()
