# -*- coding: utf-8 -*-

# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import mock
import time
from StringIO import StringIO
import subprocess
import unittest
import logging
import os.path
import sys

import etcd.client

import metaswitch.clearwater.config_manager.config_access as config_access
from clearwater_etcd_plugins.clearwater_config_access import shared_config_config_plugin

class TestClass:
    """This class is used to create an instance for the mock.return_value of
    load_plugins_in_dir"""
    def __init__(self, n):
        self.name = n
        self.help_info = 'help'
        self.file_download_name = 'thisone'


class TestClass2:
    """This class is used to create an instance for the mock.return_value of
    load_plugins_in_dir"""
    def __init__(self, n):
        self.name = n
        self.help_info = 'help'
        self.file_download_name = 'not'


class TestCheckConnection(unittest.TestCase):
    @mock.patch("metaswitch.clearwater.config_manager.config_access.subprocess.check_call",
                side_effect=subprocess.CalledProcessError(101, "fake"))
    def test_check_connection_exception(self, mock_subprocess_check_call):
        """Check that we raise a subprocess.CalledProcessError exception if the
        etcd process is not running."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_client.host = "host"
        etcd_client.port = "0000"

        with self.assertRaises(config_access.EtcdConnectionFailed):
            config_access.ConfigLoader(etcd_client, "clearwater", "site")


@mock.patch(
    "metaswitch.clearwater.config_manager.config_access.subprocess.check_output")
@mock.patch(
    "metaswitch.clearwater.config_manager.config_access.ConfigLoader._check_connection")
@mock.patch("metaswitch.clearwater.config_manager.config_access.etcd.client.Client",
            autospec=True)
class TestCheckClusterHealth(unittest.TestCase):
    def test_check_cluster_healthy(self,
                                   mock_etcd,
                                   mock_connection,
                                   mock_output):
        """Check that if the cluster is healthy, we don't throw an exception.
        """
        mock_output.return_value = """
member 2218b3ecf31a3664 is healthy: got healthy result from http://10.225.166.116:4000
member ca7f6c28e15bd223 is healthy: got healthy result from http://10.225.166.114:4000
member fe3cbfd7b0e1c068 is healthy: got healthy result from http://10.225.166.115:4000
cluster is healthy"""

        config_access.ConfigLoader(mock_etcd,
                                   "clearwater",
                                   "site")

        # If we raise an EtcdNoQuorum exception, Something has gone wrong.
        mock_output.assert_called_once()

    def test_check_cluster_unhealthy(self,
                                     mock_etcd,
                                     mock_connection,
                                     mock_output):
        """Test that if our health check indicates that the cluster is
        unhealthy, we throw an exception."""
        # For each of these return values, we should expect an exception to be
        # thrown.
        mock_output.side_effect = [
            """member 2218b3ecf31a3664 is unhealthy: got unhealthy result from http://10.225.166.116:4000
            member ca7f6c28e15bd223 is healthy: got healthy result from http://10.225.166.114:4000
            member fe3cbfd7b0e1c068 is healthy: got healthy result from http://10.225.166.115:4000
            cluster is unhealthy""",
            """member 2218b3ecf31a3664 is unhealthy: got unhealthy result from http://10.225.166.116:4000
            member ca7f6c28e15bd223 is healthy: got healthy result from http://10.225.166.114:4000
            member fe3cbfd7b0e1c068 is healthy: got healthy result from http://10.225.166.115:4000
            cluster may be unhealthy"""]

        with self.assertRaises(config_access.EtcdNoQuorum):
            config_access.ConfigLoader(mock_etcd,
                                       "clearwater",
                                       "site")

        with self.assertRaises(config_access.EtcdNoQuorum):
            config_access.ConfigLoader(mock_etcd,
                                       "clearwater",
                                       "site")

    def test_check_no_healthcheck(self,
                                  mock_etcd,
                                  mock_connection,
                                  mock_output):
        """Test that if we can't run the healthcheck we throw an error."""
        mock_output.side_effect = subprocess.CalledProcessError(1, 'command')

        with self.assertRaises(config_access.EtcdNoQuorum):
            config_access.ConfigLoader(mock_etcd,
                                       "clearwater",
                                       "site")


@mock.patch("metaswitch.clearwater.config_manager.config_access.ConfigLoader._check_connection")
@mock.patch("metaswitch.clearwater.config_manager.config_access.ConfigLoader._check_etcd_cluster_health")
@mock.patch("metaswitch.clearwater.config_manager.config_access.LocalStore",
            autospec=True)
@mock.patch("clearwater_etcd_plugins.clearwater_config_access.shared_config_config_plugin.SharedConfig", autospec=True)
class TestConfigLoader(unittest.TestCase):
    def test_download_unable_to_save(self,
                                     mock_selected_config,
                                     mock_localstore,
                                     mock_healthcheck,
                                     mock_check_connection):
        """Check for the correct exception on failure.

        Check that failing to save the config/index file causes the correct
        exception to be raised."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        mock_localstore.download_dir = "/some/directory"
        mock_localstore.save_config_and_revision.side_effect = IOError
        mock_selected_config.name = "shared_config"

        config_loader = config_access.ConfigLoader(etcd_client,
                                                   "clearwater",
                                                   "site")

        with self.assertRaises(config_access.ConfigDownloadFailed):
            config_loader.download_config(mock_localstore, mock_selected_config)

    @mock.patch("metaswitch.clearwater.config_manager.config_access.ConfigLoader.get_config_and_index")
    def test_download_gets_unicode(self,
                                   mock_get_config_and_index,
                                   mock_selected_config,
                                   mock_localstore,
                                   mock_healthcheck,
                                   mock_check_connection):
        """check that a unicode return from get_config_and_index to value is
        able to be interpreted"""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        mock_selected_config.name = "shared_config"
        mock_get_config_and_index.return_value = (u"UNICODE YAY £☃ ", 2)
        config_loader = config_access.ConfigLoader(etcd_client,
                                                   "clearwater",
                                                   "site")
        config_loader.download_config(mock_localstore, mock_selected_config)

    def test_get_config(self,
                        mock_selected_config,
                        mock_localstore,
                        mock_healthcheck,
                        mock_check_connection):
        """Check we use the right URI to download config."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_result = mock.MagicMock()
        etcd_result.value = "Some Config"
        etcd_result.modifiedIndex = 123
        etcd_client.read.return_value = etcd_result
        mock_selected_config.name = "shared_config"

        config_loader = config_access.ConfigLoader(
            etcd_client, "clearwater", "site")

        config, index = config_loader.get_config_and_index(mock_selected_config)

        self.assertEqual(config, "Some Config")
        self.assertEqual(index, 123)
        etcd_client.read.assert_called_with(
            "/clearwater/site/configuration/shared_config")

    def test_get_new_config(self,
                            mock_selected_config,
                            mock_localstore,
                            mock_healthcheck,
                            mock_check_connection):
        """Check we create a blank file if there's nothing to download."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_client.read.side_effect = etcd.EtcdKeyNotFound

        config_loader = config_access.ConfigLoader(
            etcd_client, "clearwater", "site")
        mock_selected_config.name = "fallback_ifcs"

        config, index = config_loader.get_config_and_index(mock_selected_config)

        self.assertEqual(config, "")
        self.assertEqual(index, 0)
        etcd_client.read.assert_called_with(
            "/clearwater/site/configuration/fallback_ifcs")

    def test_get_config_failed(self,
                               mock_selected_config,
                               mock_localstore,
                               mock_healthcheck,
                               mock_check_connection):
        """Check we get the right exception on failure."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_client.read.side_effect = etcd.EtcdKeyNotFound
        config_loader = config_access.ConfigLoader(
            etcd_client, "clearwater", "site")
        mock_selected_config.name = "dns_json"

        config, revision = config_loader.get_config_and_index(mock_selected_config)
        self.assertEqual(config, "")
        self.assertEqual(revision, 0)

    def test_write_config_to_etcd(self,
                                  mock_selected_config,
                                  mock_localstore,
                                  mock_healthcheck,
                                  mock_check_connection):
        """Check that we can write config to etcd from file."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)

        mock_localstore.load_config_and_revision.return_value = ("Fake Config",
                                                                 1000)
        mock_selected_config.file_download_name = "shared_config"
        mock_selected_config.name = "shared_config"
        config_loader = config_access.ConfigLoader(
            etcd_client, "clearwater", "site")

        # Need to provide a cas revision on etcd uploads to avoid conflicts.
        config_loader.write_config_to_etcd(mock_localstore, mock_selected_config, 123, 'Fake Config')

        etcd_client.write.assert_called_with(
            "/clearwater/site/configuration/shared_config",
            "Fake Config",
            prevIndex=123
        )

    def test_write_new_config_to_etcd(self,
                                      mock_selected_config,
                                      mock_localstore,
                                      mock_healthcheck,
                                      mock_check_connection):
        """Check that we can write config to etcd from file."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)

        mock_localstore.load_config_and_revision.return_value = ("Fake Config",
                                                                 0)
        mock_selected_config.name = "shared_config"
        config_loader = config_access.ConfigLoader(
            etcd_client, "clearwater", "site")

        # This is new config.
        config_loader.write_config_to_etcd(mock_localstore,
                                           mock_selected_config,
                                           0,
                                           'Fake Config')

        # When the config is new, we don't pass in a prev_revision.
        etcd_client.write.assert_called_with(
            "/clearwater/site/configuration/shared_config",
            "Fake Config"
        )

    def test_write_to_etcd_failure(self,
                                   mock_selected_config,
                                   mock_localstore,
                                   mock_healthcheck,
                                   mock_check_connection):
        """Check for the correct exception on failure.

        Check that failing to connect to etcd causes the correct
        exception to be raised."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_client.write.side_effect = [etcd.EtcdConnectionFailed,
                                         etcd.EtcdCompareFailed]

        mock_localstore.load_config_and_revision.return_value = ("LocalConfig",
                                                                 100)
        mock_selected_config.name = "shared_config"
        mock_selected_config.file_download_name = "shared_config"
        mock_config_file = mock.MagicMock()
        mock_config_file.read.return_value = "FakeConfig"

        def fake_open(file, mode):
            if file == "/home/ubuntu/clearwater-config-manager/ubuntu/shared_config":
                return mock_config_file
            else:
                self.fail("Incorrect File Accessed: {}".format(file))

        mock_open = mock.MagicMock(side_effect=fake_open)

        config_loader = config_access.ConfigLoader(etcd_client,
                                                   "clearwater",
                                                   "site")

        with mock.patch("metaswitch.clearwater.config_manager.config_access.open",
                        mock_open):
            # First time, we trigger etcd.EtcdConnectionFailed
            self.assertRaises(
                config_access.ConfigUploadFailed,
                config_loader.write_config_to_etcd,
                mock_localstore,
                mock_selected_config,
                1234, 'Fake Config')

            # Second time, we trigger etcd.EtcdCompareFailed
            self.assertRaises(
                config_access.ConfigUploadFailed,
                config_loader.write_config_to_etcd,
                mock_localstore,
                mock_selected_config,
                1234, 'Fake Config')


@mock.patch("metaswitch.clearwater.config_manager.config_access.os.path.exists",
            return_value=True)
@mock.patch("metaswitch.clearwater.config_manager.config_access.os.makedirs")
@mock.patch("metaswitch.clearwater.config_manager.config_access.os.getenv",
            return_value="/home/dir")
@mock.patch("metaswitch.clearwater.config_manager.config_access.subprocess.check_output",
            return_value="someuser")
class TestCreateLocalStore(unittest.TestCase):
    @mock.patch("metaswitch.clearwater.config_manager.config_access.reset_file_ownership")
    def test_folder_doesnt_exist(self,
                                 mock_reset,
                                 mock_subprocess,
                                 mock_getenv,
                                 mock_mkdir,
                                 mock_exists):
        """Make sure we do create a folder if there isn't one already."""
        mock_exists.return_value = False
        config_access.LocalStore()
        mock_mkdir.assert_called_once_with("/home/dir/clearwater-config-manager/someuser")

    def test_folder_exists(self, mock_subprocess, mock_getenv, mock_mkdir, mock_exists):
        """Make sure that we don't try to create a folder if one already
        exists."""
        config_access.LocalStore()
        self.assertFalse(mock_mkdir.called)

    def test_non_standard_folder(self, mock_subprocess, mock_getenv, mock_mkdir, mock_exists):
        """Check that we can handle a non-standard directory."""
        config_access.LocalStore("/tmp")
        self.assertEqual(mock_mkdir.call_count, 0)
        self.assertEqual(mock.call("/tmp"),
                         mock_exists.call_args_list[0])

@mock.patch(
    "metaswitch.clearwater.config_manager.config_access.get_user_download_dir",
    return_value="/some/directory")
@mock.patch(
    "metaswitch.clearwater.config_manager.config_access.read_from_file")
@mock.patch(
    "metaswitch.clearwater.config_manager.config_access.LocalStore._ensure_config_dir")
@mock.patch("clearwater_etcd_plugins.clearwater_config_access.shared_config_config_plugin.SharedConfig", autospec=True)
class TestLocalStore(unittest.TestCase):
    # The directory here should match the patched return value of
    # `get_user_download_dir()` above.
    CONFIG_FILE = "/some/directory/shared_config"
    REVISION_FILE = "/some/directory/.shared_config.index"

    @mock.patch(
        "metaswitch.clearwater.config_manager.config_access.os.path.exists",
        return_value=True)
    def test_config_load(self,
                         mock_exists,
                         mock_selected_config,
                         mock_ensure_dir,
                         mock_file_read,
                         mock_config_path):
        """Test that we can load from file successfully."""
        local_store = config_access.LocalStore()

        # First return example config, then return example revision number.
        mock_file_read.side_effect = ["fake_key=fake_value", 12345]

        # We don't expect there to be any asserts.
        config, revision = local_store.load_config_and_revision(
            "shared_config")

    def test_no_config_to_load(self, mock_selected_config, mock_ensure_dir,
                               mock_file_read, mock_config_path):
        """Test that we raise the right exception if there is no config file to
        load."""
        def no_config_exists(file_name):
            if file_name == self.CONFIG_FILE:
                return False
            else:
                return True

        local_store = config_access.LocalStore()
        with mock.patch("metaswitch.clearwater.config_manager.config_access.os.path.exists",
                        no_config_exists):
            with self.assertRaises(IOError):
                local_store.load_config_and_revision("shared_config")

    def test_no_index_to_load(self, mock_selected_config, mock_ensure_dir,
                              mock_file_read, mock_config_path):
        """Test that we raise the right exception if there is no index file to
        load."""
        def no_config_exists(file_name):
            if file_name == self.REVISION_FILE:
                return False
            else:
                return True

        local_store = config_access.LocalStore()
        with mock.patch("metaswitch.clearwater.config_manager.config_access.os.path.exists",
                        no_config_exists):
            with self.assertRaises(IOError):
                local_store.load_config_and_revision("shared_config")

    @mock.patch(
        "metaswitch.clearwater.config_manager.config_access.os.path.exists",
        return_value=True)
    def test_load_non_integer(self,
                              mock_exists,
                              mock_selected_config,
                              mock_ensure_dir,
                              mock_read_from_file,
                              mock_config_path):
        """Test that we raise the right exception if we try to load a
        non-integer"""
        mock_read_from_file.return_value = "not an integer"

        local_store = config_access.LocalStore()
        with self.assertRaises(config_access.InvalidRevision):
            local_store.load_config_and_revision("shared_config")

    @mock.patch("metaswitch.clearwater.config_manager.config_access.reset_file_ownership")
    def test_save_config_and_revision(self,
                                      mock_selected_config,
                                      mock_ensure_dir,
                                      mock_file_read,
                                      mock_config_path,
                                      mock_ownership):
        """Check that we correctly write to file when saving off config and
        revision data."""
        local_store = config_access.LocalStore()
        mock_selected_config.file_download_name = "shared_config"
        mock_file_open = mock.mock_open()
        with mock.patch("metaswitch.clearwater.config_manager.config_access.open",
                        mock_file_open,
                        create=True):
            local_store.save_config_and_revision(mock_selected_config,
                                                 42,
                                                 "config_text")

        assert mock.call().write("config_text") in mock_file_open.mock_calls
        assert mock.call().write(42) in mock_file_open.mock_calls

    def test_unable_to_save_config_file(self,
                                        mock_selected_config,
                                        mock_ensure_dir,
                                        mock_file_read,
                                        mock_config_path):
        """Test that we raise the right exception if we are unable to save the
        config or index file."""
        local_store = config_access.LocalStore()

        mock_config_file = mock.MagicMock()
        mock_index_file = mock.MagicMock()
        mock_config_file.__enter__.return_value = mock_config_file
        mock_index_file.__enter__.return_value = mock_index_file
        mock_selected_config.file_download_name = "shared_config"

        def fake_open(filename, mode):
            if filename == self.CONFIG_FILE:
                raise IOError
            if filename == self.REVISION_FILE:
                return mock_index_file
            else:
                self.fail("Incorrect File Accessed: {}".format(filename))

        mock_open = mock.MagicMock(side_effect=fake_open)

        with mock.patch("metaswitch.clearwater.config_manager.config_access.open", mock_open):
            with self.assertRaises(config_access.UnableToSaveFile):
                local_store.save_config_and_revision(mock_selected_config, 42,
                                                     "config_text")

    def test_unable_to_save_revision_file(self,
                                          mock_selected_config,
                                          mock_ensure_dir,
                                          mock_file_read,
                                          mock_config_path):
        """Test that we raise the right exception if we are unable to save the
        config or index file."""
        local_store = config_access.LocalStore()

        mock_config_file = mock.MagicMock()
        mock_index_file = mock.MagicMock()
        mock_config_file.__enter__.return_value = mock_config_file
        mock_index_file.__enter__.return_value = mock_index_file
        mock_selected_config.file_download_name = "shared_config"

        def fake_open(filename, mode):
            if filename == self.CONFIG_FILE:
                return mock_config_file
            if filename == self.REVISION_FILE:
                raise IOError
            else:
                self.fail("Incorrect File Accessed: {}".format(filename))

        mock_open = mock.MagicMock(side_effect=fake_open)

        with mock.patch("metaswitch.clearwater.config_manager.config_access.open", mock_open):
            with self.assertRaises(config_access.UnableToSaveFile):
                local_store.save_config_and_revision(mock_selected_config, 42,
                                                     "config_text")

    def test_config_location(self, mock_selected_config, mock_ensure_dir,
                             mock_file_read, mock_config_path):
        """Test that we can return the correct config location."""
        local_store = config_access.LocalStore()

        config_location = local_store.config_location("shared_config")
        assert config_location == "/some/directory/shared_config"


@mock.patch('metaswitch.clearwater.config_manager.config_access.raw_input')
class TestYesNo(unittest.TestCase):
    """Test user input validation."""
    def test_yes(self, mock_raw_input):
        """tests a yes input to the confirm function returns true"""
        mock_raw_input.return_value = 'yes'
        answer = config_access.confirm_yn('Test 1 ', False)
        self.assertIs(answer, True)

    def test_no(self, mock_raw_input):
        """tests a no input to the confirm function returns false"""
        mock_raw_input.return_value = 'no'
        answer = config_access.confirm_yn('Test 2 ', False)
        self.assertIs(answer, False)

    def test_skip(self, mock_raw_input):
        """checks that inputting autoskip as
         true returns true even with a no input"""
        mock_raw_input.return_value = 'no'
        answer = config_access.confirm_yn('Test 3 ', True)
        self.assertIs(answer, True)

    def test_upper_yes(self, mock_raw_input):
        """Checks the yes input can have upper case"""
        mock_raw_input.return_value = 'YeS'
        answer = config_access.confirm_yn('Test 4 ', False)
        self.assertIs(answer, True)

    def test_upper_no(self, mock_raw_input):
        """checks the no input can have upper case"""
        mock_raw_input.return_value = 'nO'
        answer = config_access.confirm_yn('Test 5 ', False)
        self.assertIs(answer, False)

    def test_wrong_in1(self, mock_raw_input):
        """checks the function asks for further inputs until a correct
        response is supplied, also checks that 'y' is acceptable"""
        mock_raw_input.side_effect = ['noo', 'yese', '1', '2e', 'y', 'notneed']
        answer = config_access.confirm_yn('Test 6 ', False)
        self.assertEqual(mock_raw_input.call_count, 5)
        self.assertIs(answer, True)

    def test_wrong_in2(self, mock_raw_input):
        """A second check for checking the function asks for correct responses
        until one is supplied, also checks that 'n' is accpetable"""
        mock_raw_input.side_effect = ['AS', '1WY1', 'Y3s', 'fo{}', '[]2e', 'n']
        answer = config_access.confirm_yn('Test 7 ', False)
        self.assertEqual(mock_raw_input.call_count, 6)
        self.assertIs(answer, False)


@mock.patch("metaswitch.clearwater.config_manager.config_access.get_user_name",
            return_value="username")
@mock.patch(
    "metaswitch.clearwater.config_manager.config_access.configure_syslog")
@mock.patch("metaswitch.clearwater.config_manager.config_access.ConfigLoader",
            autospec=True)
@mock.patch("metaswitch.clearwater.config_manager.config_access.LocalStore",
            autospec=True)
@mock.patch(
    "metaswitch.clearwater.config_manager.config_access.download_config")
@mock.patch("metaswitch.clearwater.config_manager.config_access.load_plugins_in_dir")
@mock.patch("metaswitch.clearwater.config_manager.config_access.lookup_config_type")
class TestMainDownload(unittest.TestCase):
    @mock.patch("metaswitch.clearwater.config_manager."
                "config_access.delete_outdated_config_files")
    def test_delete_outdated_config_files(self,
                                          mock_delete_files,
                                          mock_lookup_config,
                                          mock_loadplugins,
                                          mock_download_config,
                                          mock_localstore,
                                          mock_configloader,
                                          mock_logging,
                                          mock_username):
        """Make sure we always delete outdated config files"""
        args = mock.Mock()
        filename = mock.Mock()
        config_access.main(args, filename)

        mock_delete_files.assert_called_with()

    def test_download_action_main_line(self,
                                       mock_lookup_config,
                                       mock_loadplugins,
                                       mock_download_config,
                                       mock_localstore,
                                       mock_configloader,
                                       mock_logging,
                                       mock_username):
        """Make sure that we always call download_config in download mode."""
        args = mock.Mock(action='download')
        filename = mock.Mock()
        config_access.main(args, filename)

        assert mock_download_config.called

    def test_handle_download_configdownloadfailed(self,
                                                  mock_lookup_config,
                                                  mock_loadplugins,
                                                  mock_download_config,
                                                  mock_localstore,
                                                  mock_configloader,
                                                  mock_logging,
                                                  mock_username):
        """Check that we handle a ConfigDownloadFailed exception raised by
        download_config."""
        mock_download_config.side_effect = config_access.ConfigDownloadFailed
        args = mock.Mock(action='download')
        filename = mock.Mock()

        with self.assertRaises(SystemExit):
            config_access.main(args, filename)

    def test_handle_download_userabort(self,
                                       mock_lookup_config,
                                       mock_loadplugins,
                                       mock_download_config,
                                       mock_localstore,
                                       mock_configloader,
                                       mock_logging,
                                       mock_username):
        """Check that we handle a UserAbort exception raised by
        download_config."""
        mock_download_config.side_effect = config_access.UserAbort
        args = mock.Mock(action='download')
        filename = mock.Mock()

        with self.assertRaises(SystemExit):
            config_access.main(args, filename)


@mock.patch("metaswitch.clearwater.config_manager.config_access.get_user_name",
            return_value="username")
@mock.patch(
    "metaswitch.clearwater.config_manager.config_access.configure_syslog")
@mock.patch("metaswitch.clearwater.config_manager.config_access.ConfigLoader",
            autospec=True)
@mock.patch("metaswitch.clearwater.config_manager.config_access.LocalStore",
            autospec=True)
@mock.patch("metaswitch.clearwater.config_manager.config_access.lookup_config_type")
@mock.patch("metaswitch.clearwater.config_manager.config_access.upload_verified_config")
@mock.patch("metaswitch.clearwater.config_manager.config_access.load_plugins_in_dir")
class TestMainUpload(unittest.TestCase):
    def test_upload_action_main_line(self,
                                     mock_loadplugins,
                                     mock_upload_config,
                                     mock_lookup_config,
                                     mock_localstore,
                                     mock_configloader,
                                     mock_logging,
                                     mock_username):
        """Make sure that we always call upload_verified_config in upload mode."""
        args = mock.Mock(action='upload')
        filename = mock.Mock()
        config_access.main(args, filename)

        assert mock_upload_config.called

    def test_handle_upload_failed(self,
                                  mock_loadplugins,
                                  mock_upload_config,
                                  mock_lookup_config,
                                  mock_localstore,
                                  mock_configloader,
                                  mock_logging,
                                  mock_username):
        """Check that we handle an exception raised by upload_verified_config.
        """
        mock_upload_config.side_effect = config_access.ConfigUploadFailed
        args = mock.Mock(action='upload')
        filename = mock.Mock()

        with self.assertRaises(SystemExit):
            config_access.main(args, filename)

    def test_handle_upload_configuploadfailed(self,
                                              mock_loadplugins,
                                              mock_upload_config,
                                              mock_lookup_config,
                                              mock_localstore,
                                              mock_configloader,
                                              mock_logging,
                                              mock_username):
        """Check that we handle a ConfigUploadFailed exception raised by
        upload_verified_config."""
        mock_upload_config.side_effect = config_access.ConfigUploadFailed
        args = mock.Mock(action='upload')
        filename = mock.Mock()

        with self.assertRaises(SystemExit):
            config_access.main(args, filename)

    @mock.patch('metaswitch.clearwater.config_manager.config_access.sys.exit')
    def test_handle_upload_no_change(self,
                                     mock_sysexit,
                                     mock_loadplugins,
                                     mock_upload_config,
                                     mock_lookup_config,
                                     mock_localstore,
                                     mock_configloader,
                                     mock_logging,
                                     mock_username):
        """Check that we handle a ConfigUploadFailed exception raised by
        upload_verified_config."""
        mock_upload_config.side_effect = config_access.ConfigUnchanged
        args = mock.Mock(action='upload')
        filename = mock.Mock()

        config_access.main(args, filename)

        # We should not have called through to sys.exit() because the test
        # has not failed.
        self.assertEqual(mock_sysexit.call_count, 0)

    def test_handle_upload_configvalidationfailed(self,
                                                  mock_loadplugins,
                                                  mock_upload_config,
                                                  mock_lookup_config,
                                                  mock_localstore,
                                                  mock_configloader,
                                                  mock_logging,
                                                  mock_username):
        """Check that we handle a ConfigValidationFailed exception raised by
        upload_verified_config."""
        mock_upload_config.side_effect = config_access.ConfigValidationFailed
        args = mock.Mock(action='upload')
        filename = mock.Mock()

        with self.assertRaises(SystemExit):
            config_access.main(args, filename)

    def test_handle_upload_userabort(self,
                                     mock_loadplugins,
                                     mock_upload_config,
                                     mock_lookup_config,
                                     mock_localstore,
                                     mock_configloader,
                                     mock_logging,
                                     mock_username):
        """Check that we handle a UserAbort exception raised by
        upload_verified_config."""
        mock_upload_config.side_effect = config_access.UserAbort
        args = mock.Mock(action='upload')
        filename = mock.Mock()

        with self.assertRaises(SystemExit):
            config_access.main(args, filename)

    def test_handle_etcdexception(self,
                                  mock_loadplugins,
                                  mock_upload_config,
                                  mock_lookup_config,
                                  mock_localstore,
                                  mock_configloader,
                                  mock_logging,
                                  mock_username):
        """Check that we handle an EtcdException raised by
        etcd.client.Client."""
        mock_configloader.side_effect = etcd.EtcdException
        args = mock.Mock(action='upload')
        filename = mock.Mock()

        with self.assertRaises(SystemExit):
            config_access.main(args, filename)

    def test_handle_etcdquorumfail(self,
                                   mock_loadplugins,
                                   mock_upload_config,
                                   mock_lookup_config,
                                   mock_localstore,
                                   mock_configloader,
                                   mock_logging,
                                   mock_username):
        """Check that we handle a lack of Etcd quorum."""
        mock_configloader.side_effect = config_access.EtcdNoQuorum
        args = mock.Mock(action='upload')
        filename = mock.Mock()

        with self.assertRaises(SystemExit):
            config_access.main(args, filename)


@mock.patch("metaswitch.clearwater.config_manager.config_access.get_user_download_dir")
@mock.patch("metaswitch.clearwater.config_manager.config_access.confirm_yn")
@mock.patch("metaswitch.clearwater.config_manager.config_access.os.path.exists")
class TestConfigDownload(unittest.TestCase):
    def test_confirm_overwrite(self, mock_path_exists, mock_confirm_yn, mock_download_dir):
        """Check that we ask the user for confirmation before overwriting an
        existing file."""
        mock_path_exists.return_value = True
        config_access.download_config(mock.Mock(), mock.Mock(), mock.Mock())

        assert mock_confirm_yn.called

    def test_deny_overwrite(self, mock_path_exists, mock_confirm_yn, mock_download_dir):
        """Check that we raise a UserAbort exception if the user denies to
        overwrite an existing file."""
        mock_path_exists.return_value = True
        mock_confirm_yn.return_value = False

        with self.assertRaises(config_access.UserAbort):
            config_access.download_config(mock.Mock(), mock.Mock(), mock.Mock())

    @mock.patch(
        "metaswitch.clearwater.config_manager.config_access.ConfigLoader",
        spec=True)
    def test_allow_overwrite(self,
                             mock_path_exists,
                             mock_confirm_yn,
                             mock_download_dir,
                             mock_configloader):
        """Check that we don't raise a UserAbort exception if the user allows
        to overwrite an existing file and check that we download_config."""
        mock_path_exists.return_value = True
        mock_confirm_yn.return_value = True

        config_access.download_config(mock.Mock(), mock.Mock(), mock.Mock())

        mock_configloader.download_config.assert_called_once

@mock.patch(
    "metaswitch.clearwater.config_manager.config_access.upload_config")
@mock.patch(
    "metaswitch.clearwater.config_manager.config_access.validate_config")
@mock.patch(
    "metaswitch.clearwater.config_manager.config_access.os.path")
class TestVerifiedUpload(unittest.TestCase):

    def test_only_upload_validated_config(self,
                                          mock_os,
                                          mock_validate_config,
                                          mock_upload_config):
        """Check that we only call upload_config if validation passed."""
        mock_configloader = mock.MagicMock(spec=config_access.ConfigLoader)
        mock_localstore = mock.MagicMock(spec=config_access.LocalStore)
        mock_selectedconfig = mock.MagicMock(
            spec=shared_config_config_plugin.SharedConfig)
        mock_os.exists.return_value = True

        # Test that if we fail to validate the config, it does not get
        # uploaded.
        mock_validate_config.side_effect = config_access.ConfigValidationFailed
        with self.assertRaises(config_access.ConfigValidationFailed):
            config_access.upload_verified_config(mock_configloader,
                                                 mock_localstore,
                                                 mock_selectedconfig,
                                                 "shared_config")
        assert not mock_upload_config.called

        # Test that if we successfully validate the config, it does get
        # uploaded.
        mock_validate_config.side_effect = None
        config_access.upload_verified_config(mock_configloader,
                                             mock_localstore,
                                             mock_selectedconfig,
                                             "shared_config")

        assert mock_upload_config.called

    def test_no_file_to_upload(self,
                               mock_os,
                               mock_validate_config,
                               mock_upload_config):
        mock_configloader = mock.MagicMock(spec=config_access.ConfigLoader)
        mock_localstore = mock.MagicMock(spec=config_access.LocalStore)
        mock_selectedconfig = mock.MagicMock(
            spec=shared_config_config_plugin.SharedConfig)
        mock_os.exists.return_value = False
        with self.assertRaises(config_access.ConfigUploadFailed):
            config_access.upload_verified_config(mock_configloader,
                                                 mock_localstore,
                                                 mock_selectedconfig,
                                                 "shared_config")


@mock.patch("clearwater_etcd_plugins.clearwater_config_access.shared_config_config_plugin.SharedConfig", autospec=True)
class TestValidation(unittest.TestCase):

    def test_handle_validation_error(self, mock_selected_config):
        """Test that we handle validation failure correctly."""
        mock_selected_config.validate.return_value = (['script1'], [])

        # A script has failed and is in failed_scripts.
        with self.assertRaises(config_access.ConfigValidationFailed):
            config_access.validate_config(mock_selected_config, False)

    def test_ignore_validation_error(self, mock_selected_config):
        """Test that we ignore validation failure correctly in the force
        case."""
        mock_selected_config.validate.return_value = (['script1'], [])
        # Even though subprocess raises an exception, we continue because
        # we're in force mode.
        config_access.validate_config(mock_selected_config, True)

    def test_no_errors(self, mock_selected_config):
        """test everything runs ok when it returns no errors"""
        mock_selected_config.validate.return_value = ([], ['script1'])
        config_access.validate_config(mock_selected_config, False)


@mock.patch("metaswitch.clearwater.config_manager.config_access.ConfigLoader",
            autospec=True)
@mock.patch("metaswitch.clearwater.config_manager.config_access.LocalStore",
            autospec=True)
@mock.patch("clearwater_etcd_plugins.clearwater_config_access.shared_config_config_plugin.SharedConfig", autospec=True)
class TestReadyForUpload(unittest.TestCase):
    def test_upload_unable_to_load(self,
                                   mock_selected_config,
                                   mock_localstore,
                                   mock_configloader):
        """Check that we raise a ConfigUploadFailed exception if we can't load
        the config and index."""
        # Throw an error when loading the config.
        mock_localstore.load_config_and_revision.side_effect = IOError
        mock_selected_config.file_download_name = "shared_config"

        with self.assertRaises(config_access.ConfigUploadFailed):
            config_access.ready_for_upload_checks(False,
                                                  mock_configloader,
                                                  mock_selected_config,
                                                  mock_localstore)

    def test_cant_download_config(self,
                                  mock_selected_config,
                                  mock_localstore,
                                  mock_configloader):
        """Check that if we can't download config to compare, we raise an
        exception."""

        mock_localstore.load_config_and_revision.return_value = (
            "local_config_text", 41)
        mock_configloader.get_config_and_index.side_effect = config_access.ConfigDownloadFailed
        mock_selected_config.file_download_name = "shared_config"
        with self.assertRaises(config_access.ConfigUploadFailed):
            config_access.ready_for_upload_checks(False,
                                                  mock_configloader,
                                                  mock_selected_config,
                                                  mock_localstore)

    def test_different_revision_numbers(self,
                                        mock_selected_config,
                                        mock_localstore,
                                        mock_configloader):
        """Check that we raise an exception if the local revision is not the
        same as the remote revision."""
        mock_localstore.load_config_and_revision.return_value = (
            "local_config_text", 41)
        mock_configloader.get_config_and_index.return_value = (
            "remote_config_text", 42)
        mock_selected_config.file_download_name = "shared_config"

        with self.assertRaises(config_access.ConfigUploadFailed):
            config_access.ready_for_upload_checks(False,
                                                  mock_configloader,
                                                  mock_selected_config,
                                                  mock_localstore)

    @mock.patch(
        "metaswitch.clearwater.config_manager.config_access.print_diff_and_syslog",
        return_value=False)
    def test_no_config_changes(self,
                               mock_diff,
                               mock_selected_config,
                               mock_localstore,
                               mock_configloader):
        """Check that we raise an exception if no changes were made."""

        mock_localstore.load_config_and_revision.return_value = (
            "same_config_text", 41)
        mock_configloader.get_config_and_index.return_value = (
            "same_config_text", 41)
        mock_selected_config.file_download_name = "shared_config"

        with self.assertRaises(config_access.ConfigUploadFailed):
            config_access.ready_for_upload_checks(False,
                                                  mock_configloader,
                                                  mock_selected_config,
                                                  mock_localstore)

    @mock.patch("metaswitch.clearwater.config_manager.config_access.confirm_yn",
                return_value=True)
    @mock.patch(
        "metaswitch.clearwater.config_manager.config_access.print_diff_and_syslog",
        return_value=True)
    def test_ask_confirmation(self,
                              mock_diff,
                              mock_confirm,
                              mock_selected_config,
                              mock_localstore,
                              mock_configloader):
        """Check that we ask for user confirmation if and only if
        autoconfirm is False."""

        mock_localstore.load_config_and_revision.return_value = (
            "local_config_text", 41)
        mock_configloader.get_config_and_index.return_value = (
            "remote_config_text", 41)
        mock_selected_config.file_download_name = "shared_config"

        # First test that no user confirmation is required if we are
        # autoconfirming.
        config_access.ready_for_upload_checks(True,
                                              mock_configloader,
                                              mock_selected_config,
                                              mock_localstore)
        self.assertIs(mock_confirm.call_count, 0)

        # Now test that user confirmation is required if we aren't
        # autoconfirming.
        config_access.ready_for_upload_checks(False,
                                              mock_configloader,
                                              mock_selected_config,
                                              mock_localstore)

        mock_confirm.assert_called_once()

    @mock.patch("metaswitch.clearwater.config_manager.config_access.confirm_yn",
                return_value=False)
    @mock.patch(
        "metaswitch.clearwater.config_manager.config_access.print_diff_and_syslog",
        return_value=True)
    def test_user_abort(self,
                        mock_diff,
                        mock_confirm,
                        mock_selected_config,
                        mock_localstore,
                        mock_configloader):
        """Check that we raise a UserAbort exception if autoconfirm is false
        and the user denied to continue."""

        mock_localstore.load_config_and_revision.return_value = (
            "local_config_text", 41)
        mock_configloader.get_config_and_index.return_value = (
            "remote_config_text", 41)
        mock_selected_config.file_download_name = "shared_config"

        with self.assertRaises(config_access.UserAbort):
            config_access.ready_for_upload_checks(False,
                                                  mock_configloader,
                                                  mock_selected_config,
                                                  mock_localstore)


@mock.patch("metaswitch.clearwater.config_manager.config_access.get_user_download_dir")
@mock.patch("metaswitch.clearwater.config_manager.config_access.ready_for_upload_checks",
             return_value=(1,'sdfgh'))
@mock.patch("metaswitch.clearwater.config_manager.config_access.subprocess")
@mock.patch("metaswitch.clearwater.config_manager.config_access.LocalStore._ensure_config_dir")
@mock.patch("metaswitch.clearwater.config_manager.config_access.ConfigLoader", autospec=True)
@mock.patch("metaswitch.clearwater.config_manager.config_access.os.remove")
@mock.patch("clearwater_etcd_plugins.clearwater_config_access.shared_config_config_plugin.SharedConfig", autospec=True)
class TestUpload(unittest.TestCase):
    def test_upload_config(self,
                           mock_selected_config,
                           mock_remove,
                           mock_configloader,
                           mock_ensure,
                           mock_subprocess,
                           mock_checks,
                           mock_download_dir):
        """Check that we write the config to etcd when uploading."""
        local_store = config_access.LocalStore()
        mock_selected_config.name = "shared_config"
        mock_selected_config.file_download_name = "shared_config"
        config_access.upload_config(True,
                                    mock_configloader,
                                    mock_selected_config,
                                    True,
                                    local_store)
        mock_configloader.write_config_to_etcd.assert_called_once()

    def test_remove_file_on_success(self,
                                    mock_selected_config,
                                    mock_remove,
                                    mock_config_loader,
                                    mock_ensure,
                                    mock_subprocess,
                                    mock_checks,
                                    mock_download_dir):
        """Check that we remove the local config file on successful upload."""
        download_dir = "download/dir"
        mock_download_dir.return_value = download_dir
        local_store = config_access.LocalStore()
        mock_selected_config.name = "shared_config"
        mock_selected_config.file_download_name = "shared_config"
        config_access.upload_config(False,
                                    mock_config_loader,
                                    mock_selected_config,
                                    False,
                                    local_store)

        remove_calls = [mock.call(os.path.join(download_dir,
                                               "shared_config")),
                        mock.call(os.path.join(download_dir,
                                               ".shared_config.index"))]
        mock_remove.assert_has_calls(remove_calls)


@mock.patch("metaswitch.clearwater.config_manager.config_access.os.remove")
@mock.patch("metaswitch.clearwater.config_manager.config_access.os.path.getmtime")
@mock.patch("metaswitch.clearwater.config_manager.config_access.os.walk")
class TestDeleteOutdated(unittest.TestCase):
    def test_no_delete(self, mock_walk, mock_getmtime, mock_remove):
        """This tests that a recent file is not deleted"""
        # Gives time of file creation as 28 days ago
        mock_getmtime.return_value = (time.time() - (28 * 24 * 60 * 60))
        mock_walk.return_value = (('/imaginary_file_name', [], ['testdel.py']),
                                  ('/imaginary_file_2', [], []))
        config_access.delete_outdated_config_files()
        # Need to check os.remove is NOT called
        self.assertIs(mock_remove.call_count, 0)

    def test_yes_delete(self, mock_walk, mock_getmtime, mock_remove):
        """This tests that a older file is deleted"""
        # Gives the creation time of the file at 32 days
        mock_getmtime.return_value = (time.time() - (32 * 24 * 60 * 60))
        mock_walk.return_value = (
            ('/imaginary_file_name', ['imaginary_file_2'], ['testdel.py']),
            ('/imaginary_file_name/imaginary_file_2', [], []))
        config_access.delete_outdated_config_files()
        # Need to check os.remove IS called
        self.assertIs(mock_remove.call_count, 1)


@mock.patch("metaswitch.clearwater.config_manager.config_access.os.getenv")
@mock.patch("metaswitch.clearwater.config_manager.config_access.subprocess.check_output")
class TestUserName(unittest.TestCase):
    """Tests the get_user_name() function."""
    def test_who_am_i(self, mock_subp, mock_getenv):
        """Check that we correctly return the value from `who am i`"""
        mock_subp.return_value = 'clearwater fdbngh fghj'
        username = config_access.get_user_name()
        mock_subp.assert_called_with(['who', 'am', 'i'])
        self.assertMultiLineEqual(username, 'clearwater')

    def test_os_environ(self, mock_subp, mock_getenv):
        """Check that we get information from the OS if `who am i` returns
        nothing."""
        mock_subp.return_value = ""
        mock_getenv.return_value = "user"
        username = config_access.get_user_name()
        self.assertIs(mock_getenv.call_count, 1)
        mock_getenv.assert_called_with('USER')
        self.assertMultiLineEqual(username, 'user')


class TestUserDownloadDir(unittest.TestCase):
    # """Returns the user-specific directory for downloaded config."""
    @mock.patch("metaswitch.clearwater.config_manager.config_access.get_user_name")
    @mock.patch("metaswitch.clearwater.config_manager.config_access.get_base_download_dir")
    def test_call_get_base(self, mock_getbase, mock_getuser):
        """check that we call get_base_download_dir and get_user_name """
        config_access.get_user_download_dir()
        self.assertIs(mock_getbase.call_count, 1)
        self.assertIs(mock_getuser.call_count, 1)


    @mock.patch("metaswitch.clearwater.config_manager.config_access.get_user_name")
    @mock.patch("metaswitch.clearwater.config_manager.config_access.get_base_download_dir")
    def test_call_get_base_no_username(self, mock_getbase, mock_getuser):
        """check that we call get_base_download_dir and get_user_name """
        mock_getuser.return_value = None
        mock_getbase.return_value = "/base_dir"
        user_download_dir = config_access.get_user_download_dir()
        self.assertIs(mock_getbase.call_count, 1)
        self.assertEqual(user_download_dir, "/base_dir/")


@mock.patch("metaswitch.clearwater.config_manager.config_access.os.getenv")
@mock.patch("metaswitch.clearwater.config_manager.config_access.os.getcwd")
class TestBaseDownloadDir(unittest.TestCase):
    def test_call_osgetenv(self, mock_getcwd, mock_getenv):
        """check that we call os.getenv(HOME)"""
        config_access.get_base_download_dir()
        self.assertIs(mock_getenv.call_count, 1)
        self.assertIs(mock_getcwd.call_count, 0)

    def test_no_home_dir(self, mock_getcwd, mock_getenv):
        """check that we fall back to the working directory if no home dir."""
        mock_getenv.return_value = None
        config_access.get_base_download_dir()
        self.assertIs(mock_getcwd.call_count, 1)

    def test_get_runtime_error(self, mock_getcwd, mock_getenv):
        """check that a runtime error is raised when no directory is found"""
        config_access.get_base_download_dir()
        mock_getenv.return_value = None
        mock_getcwd.return_value = None
        with self.assertRaises(RuntimeError):
            config_access.get_base_download_dir()


@mock.patch("metaswitch.clearwater.config_manager.config_access.load_plugins_in_dir")
class TestArguments(unittest.TestCase):

    def test_no_config_classes(self, mock_loadplugins):
        mock_loadplugins.return_value = []
        with self.assertRaises(SystemExit):
            config_access.parse_arguments()

    def test_all_arguments(self, mock_loadplugins):
        mock_loadplugins.return_value = [TestClass('shared_config'), TestClass2('dns_json')]
        """Test that every argument is set correctly."""
        sys.argv = ["config_access.py",
                    "--autoconfirm",
                    "--force",
                    "--log-level", "50",
                    "upload",
                    "shared_config",
                    "--management_ip", "1.2.3.4",
                    "--site", "siteX",
                    "--etcd_key", "lockpick"]

        args, config = config_access.parse_arguments()

        assert args.force
        assert args.autoconfirm
        assert args.log_level == 50
        assert args.action == "upload"
        assert args.config_type == "shared_config"
        assert args.management_ip == "1.2.3.4"
        assert args.site == "siteX"
        assert args.etcd_key == "lockpick"
        assert config == 'thisone'

    def test_mandatory_args_only(self, mock_loadplugins):
        mock_loadplugins.return_value = [TestClass('shared_config'), TestClass2('dns_json')]
        """Check that we correctly parse only the mandatory arguments."""
        sys.argv = ["config_access.py",
                    "download",
                    "dns_json",
                    "--management_ip", "1.2.3.4",
                    "--site", "siteX",
                    "--etcd_key", "lockpick"]

        args, config = config_access.parse_arguments()

        assert not args.force
        assert not args.autoconfirm
        assert args.log_level == logging.INFO
        assert args.action == "download"
        assert args.config_type == "dns_json"
        assert args.management_ip == "1.2.3.4"
        assert args.site == "siteX"
        assert args.etcd_key == "lockpick"
        assert config == 'not'

    def test_missing_args(self, mock_loadplugins):
        """Check that when the arguments are invalid we error out."""
        mock_loadplugins.return_value = [TestClass('shared_config'), TestClass('dns_json')]
        sys.argv = ["config_access.py",
                    "reload",
                    "shard_config"]

        # There's a config error, so we should fail.
        with self.assertRaises(SystemExit):
            config_access.parse_arguments()

    def test_wrong_config(self, mock_loadplugins):
        """check that when a config_type not in the choice list is provided
        a error is raised"""
        mock_loadplugins.return_value = [TestClass('shared_config'), TestClass('dns_json')]

        sys.argv = ["config_access.py",
                    "download",
                    "weatherwax_config",
                    "--management_ip", "1.2.3.4",
                    "--site", "siteX",
                    "--etcd_key", "lockpick"]

        with self.assertRaises(SystemExit):
            config_access.parse_arguments()


@mock.patch("metaswitch.clearwater.config_manager.config_access.load_plugins_in_dir")
class TestLookupConfig(unittest.TestCase):

    def test_lookup_config_type_shared(self, mock_loadplugins):
        """Check that class return returns the correct class instance of
        shared_config"""
        mock_loadplugins.return_value = [TestClass('shared_config'), TestClass2('bgcf_json')]
        key = 'shared_config'
        answer = config_access.lookup_config_type(key, 'path')
        self.assertIsInstance(answer, TestClass)

    def test_lookup_config_type_bgcf(self, mock_loadplugins):
        """Check that class return returns bgcf_json class instance
        correctly"""
        mock_loadplugins.return_value = [TestClass('shared_config'), TestClass2('bgcf_json')]
        key = 'bgcf_json'
        answer = config_access.lookup_config_type(key, 'path')
        self.assertIsInstance(answer, TestClass2)


# In these tests, we use the mock.mock_open() helper to simulate file access.
class TestReadFromFile(unittest.TestCase):
    def test_valid_read(self):
        """Tests that a normal file is read properly."""
        mock_file = mock.mock_open(read_data="some_data")

        with mock.patch('metaswitch.clearwater.config_manager.config_access.open',
                        mock_file,
                        create=True):
            config = config_access.read_from_file('example_file')

        self.assertEqual(config, "some_data")

    def test_file_too_big(self):
        """Test that if the file exceeds the maximum size an error is thrown.
        """
        mock_file = mock.mock_open(
            read_data="X" * (config_access.MAXIMUM_CONFIG_SIZE + 1))

        # By default, the mock_open() helper returns all the contents of the
        # read_data argument when the `read()` method is called. To overcome
        # this limitation, we have to mock out the file object generated by
        # mock_open() to work the way we want it to.
        mock_file.return_value = mock.MagicMock(spec=file)
        mock_file.return_value.read.side_effect = [
            "X" * config_access.MAXIMUM_CONFIG_SIZE,
            "X"]

        with mock.patch('metaswitch.clearwater.config_manager.config_access.open',
                        mock_file,
                        create=True):
            with self.assertRaises(config_access.FileTooLarge):
                config_access.read_from_file('example_file')

    def test_file_does_not_exist(self):
        """Test we throw an IOError if the file doesn't exist."""
        mock_file = mock.mock_open()
        mock_file.side_effect = IOError

        with mock.patch('metaswitch.clearwater.config_manager.config_access.open',
                        mock_file,
                        create=True):
            with self.assertRaises(IOError):
                config_access.read_from_file('example_file')


@mock.patch("metaswitch.clearwater.config_manager.config_access.os.chown")
@mock.patch("metaswitch.clearwater.config_manager.config_access.pwd.getpwnam")
@mock.patch("metaswitch.clearwater.config_manager.config_access.os.getenv")
class TestFixOwnership(unittest.TestCase):
    def test_run_as_sudo(self, mock_getenv, mock_getpwnam, mock_chown):
        """If we're being run as sudo, we should change ownership."""
        mock_getenv.return_value = "username"
        mock_getpwnam.return_value.pw_uid = 1000
        mock_getpwnam.return_value.pw_gid = 2000

        config_access.reset_file_ownership('file/path')

        mock_chown.assert_called_once_with('file/path', 1000, 2000)

    def test_not_run_as_sudo(self, mock_getenv, mock_getpwnam, mock_chown):
        """Check that we don't change ownership if we are not running as sudo.
        """
        mock_getenv.return_value = None
        config_access.reset_file_ownership('file/path')

        self.assertFalse(mock_getpwnam.called)
        self.assertFalse(mock_chown.called)

    def test_handle_failure(self, mock_getenv, mock_getpwnam, mock_chown):
        """Make sure we don't throw an error if we can't reset the permissions.
        """
        mock_chown.side_effect = OSError
        config_access.reset_file_ownership('file/path')


class MockConfigPlugin:
    def __init__(self, use_unified_diff):
        self._use_unified_diff = use_unified_diff

    def use_unified_diff(self):
        return self._use_unified_diff


@mock.patch("metaswitch.clearwater.config_manager.config_access.lookup_config_type")
class TestDiffType(unittest.TestCase):
    def test_diff_type(self, mock_config_type):
        """check that we return the correct diff type based on the underlying
        config_type object returned.
        """
        shared_config = MockConfigPlugin(False)
        json_config = MockConfigPlugin(True)

        tests = { shared_config : False,
                  json_config : True,
                  None : True }
        for plugin in tests.keys():
            mock_config_type.return_value = plugin

            answer = config_access.use_unified_diff("my_config_type")
            self.assertIs(answer, tests[plugin])


# For added realism, we use some real examples of config files in these tests.
@mock.patch("metaswitch.clearwater.config_manager.config_access.use_unified_diff", autospec=True)
@mock.patch("metaswitch.clearwater.config_manager.config_access.audit_log")
@mock.patch("metaswitch.clearwater.config_manager.config_access.get_user_name")
class TestDiffAndSyslog(unittest.TestCase):
    def test_check_iden(self, mock_username, mock_syslog, mock_unified_diff):
        """check that the diff for two identical files returns false,
        these are unicode strings to test that part of the code"""
        unicode1 = u'string is a string £☃ \n yay \n These contain unicode'
        unicode2 = u'string is a string £☃ \n yay \n These contain unicode'
        answer = config_access.print_diff_and_syslog("shared_config", unicode1,
                                                     unicode2)
        self.assertIs(answer, False)

    @mock.patch("metaswitch.clearwater.config_manager.config_access.sys.stdout",
                new_callable=StringIO)
    def test_check_diff(self, mock_stdout, mock_getname, mock_syslog, mock_unified_diff):
        """Check that for two different files with additions, deletions and
        moves the syslog_str and output_str represent the differences."""
        mock_unified_diff.return_value = False
        mock_getname.return_value = 'name'
        string1 = """# Config for deployment, local site site1
                sprout_hostname='sprout.site1.md6-clearwater.clearwater.test'
                sprout_hostname_mgmt='sprout-mgmt.site1.md6-clearwater.clearwater.test:9886'
                hs_hostname='homestead.site1.md6-clearwater.clearwater.test:8888'
                hs_hostname_mgmt='homestead-mgmt.site1.md6-clearwater.clearwater.test:8886'
                chronos_hostname='chronos.site1.md6-clearwater.clearwater.test'
                cassandra_hostname='cassandra.site1.md6-clearwater.clearwater.test'
                site_names='site1'
                sprout_registration_store='site1=astaire.site1.md6-clearwater.clearwater.test'
                alias_list='sprout.site1.md6-clearwater.clearwater.test,scscf.sprout.site1.md6-clearwater.clearwater.test,icscf.sprout.site1.md6-clearwater.clearwater.test,bgcf.sprout.site1.md6-clearwater.clearwater.test'
                sprout_chronos_callback_uri='sprout.md6-clearwater.clearwater.test'

                # DNS record found for ralf.site1.md6-clearwater.clearwater.test, so Ralf will be used
                ralf_hostname='ralf.site1.md6-clearwater.clearwater.test:10888'
                ralf_session_store='site1=astaire.site1.md6-clearwater.clearwater.test'
                ralf_chronos_callback_uri='ralf.md6-clearwater.clearwater.test'
                billing_realm='billing.md6-clearwater.clearwater.test'

                # DNS record found for SRV _diameter._tcp.md6-clearwater.clearwater.test, so assuming an external HSS in use
                hss_realm='md6-clearwater.clearwater.test'
                snmp_notification_types='enterprise'

                sas_server='sas.md6-clearwater.clearwater.test'

                # DNS record found for snmp-manager.md6-clearwater.clearwater.test, so using SNMP
                #snmp_ip='10.225.166.11'
                # DNS record found for enum.md6-clearwater.clearwater.test
                enum_server='enum.md6-clearwater.clearwater.test'


                icscf='5052'
                scscf='5054'

                hss_reregistration_time='0'
                reg_max_expires='3600'
                enforce_user_phone='Y'
                enforce_global_only_lookups='Y'

                remote_audit_logging_server="10.225.22.158:524\""""

        string2 = """# Config for deployment, local site site1
                sprout_hostname='sprout.site1.md6-clearwater.clearwater.test'
                sprout_hostname_mgmt='sprout-mgmt.site1.md6-clearwater.clearwater.test:9886'
                hs_hostname='homestead.site1.md6-clearwater.clearwater.test:8888'
                hs_hostname_mgmt='homestead-mgmt.site1.md6-clearwater.clearwater.test:8886'
                chronos_hostname='chronos.site1.md6-clearwater.clearwater.test'
                cassandra_hostname='cassandra.site1.md6-clearwater.clearwater.test'
                site_names='site1'
                sprout_registration_store='site1=astaire.site1.md6-clearwater.clearwater.test'
                alias_list='sprout.site1.md6-clearwater.clearwater.test,scscf.sprout.site1.md6-clearwater.clearwater.test,icscf.sprout.site1.md6-clearwater.clearwater.test,bgcf.sprout.site1.md6-clearwater.clearwater.test'
                sprout_chronos_callback_uri='sprout.md6-clearwater.clearwater.test'

                # DNS record found for ralf.site1.md6-clearwater.clearwater.test, so Ralf will be used
                ralf_hostname='ralf.site1.md6-clearwater.clearwater.test:10888'
                ralf_session_store='site1=astaire.site1.md6-clearwater.clearwater.test'
                ralf_chronos_callback_uri='ralf.md6-clearwater.clearwater.test'
                billing_realm='billing.md6-clearwater.clearwater.test'

                scscf='5054'

                # DNS record found for SRV _diameter._tcp.md6-clearwater.clearwater.test, so assuming an external HSS in use
                hss_realm='md6-clearwater.clearwater.test'

                icscf='5052'

                sas_server='sas.md6-clearwater.clearwater.test'

                # DNS record found for snmp-manager.md6-clearwater.clearwater.test, so using SNMP
                #snmp_ip='10.225.166.11'
                # DNS record found for enum.md6-clearwater.clearwater.test
                enum_server='enum.md6-clearwater.clearwater.test'
                snmp_notification_types='enterprise'

                hss_reregistration_time='0'
                reg_max_expires='3600'
                enforce_user_phone='Y'
                enforce_global_only_lookups='Y'

                remote_audit_logging_server="10.225.22.158:514\""""

        answer = config_access.print_diff_and_syslog("shared_config",
                                                     string1,
                                                     string2)
        self.assertIs(answer, True)
        textchanges = """Configuration file change: user name has modified shared_config.
 Lines removed:
"                remote_audit_logging_server="10.225.22.158:524""
 Lines added:
"                remote_audit_logging_server="10.225.22.158:514""
 Lines moved:
"                scscf='5054'"
"                icscf='5052'"
"                snmp_notification_types='enterprise'\"\n"""
        self.assertMultiLineEqual(mock_stdout.getvalue(), textchanges)

    def test_call_syslog(self, mock_getname, mock_syslog, mock_unified_diff):
        """check that we're audit logging the diffs"""
        mock_unified_diff.return_value = False
        mock_getname.return_value = 'name'
        string1 = """# Config for deployment, local site site1
                sprout_hostname='sprout.site1.md6-clearwater.clearwater.test'
                sprout_hostname_mgmt='sprout-mgmt.site1.md6-clearwater.clearwater.test:9886'
                hs_hostname='homestead.site1.md6-clearwater.clearwater.test:8888'
                hs_hostname_mgmt='homestead-mgmt.site1.md6-clearwater.clearwater.test:8886'
                chronos_hostname='chronos.site1.md6-clearwater.clearwater.test'
                cassandra_hostname='cassandra.site1.md6-clearwater.clearwater.test'
                site_names='site1'
                sprout_registration_store='site1=astaire.site1.md6-clearwater.clearwater.test'
                alias_list='sprout.site1.md6-clearwater.clearwater.test,scscf.sprout.site1.md6-clearwater.clearwater.test,icscf.sprout.site1.md6-clearwater.clearwater.test,bgcf.sprout.site1.md6-clearwater.clearwater.test'
                sprout_chronos_callback_uri='sprout.md6-clearwater.clearwater.test'

                # DNS record found for ralf.site1.md6-clearwater.clearwater.test, so Ralf will be used
                ralf_hostname='ralf.site1.md6-clearwater.clearwater.test:10888'
                ralf_session_store='site1=astaire.site1.md6-clearwater.clearwater.test'
                ralf_chronos_callback_uri='ralf.md6-clearwater.clearwater.test'
                billing_realm='billing.md6-clearwater.clearwater.test'

                # DNS record found for SRV _diameter._tcp.md6-clearwater.clearwater.test, so assuming an external HSS in use
                hss_realm='md6-clearwater.clearwater.test'


                sas_server='sas.md6-clearwater.clearwater.test'

                # DNS record found for snmp-manager.md6-clearwater.clearwater.test, so using SNMP
                #snmp_ip='10.225.166.11'
                # DNS record found for enum.md6-clearwater.clearwater.test
                enum_server='enum.md6-clearwater.clearwater.test'
                snmp_notification_types='enterprise'

                icscf='5052'
                scscf='5054'

                hss_reregistration_time='0'
                reg_max_expires='3600'
                enforce_user_phone='Y'
                enforce_global_only_lookups='Y'

                remote_audit_logging_server="10.225.22.158:514\""""

        string2 = """# Config for deployment, local site site1
                sprout_hostname='sprout.site1.md6-clearwater.clearwater.test'
                sprout_hostname_mgmt='sprout-mgmt.site1.md6-clearwater.clearwater.test:9886'
                hs_hostname='homestead.site1.md6-clearwater.clearwater.test:8888'
                hs_hostname_mgmt='homestead-mgmt.site1.md6-clearwater.clearwater.test:8886'
                chronos_hostname='chronos.site1.md6-clearwater.clearwater.test'
                cassandra_hostname='cassandra.site1.md6-clearwater.clearwater.test'
                site_names='site2'
                sprout_registration_store='site1=astaire.site1.md6-clearwater.clearwater.test'
                alias_list='sprout.site1.md6-clearwater.clearwater.test,scscf.sprout.site1.md6-clearwater.clearwater.test,icscf.sprout.site1.md6-clearwater.clearwater.test,bgcf.sprout.site1.md6-clearwater.clearwater.test'
                sprout_chronos_callback_uri='sprout.md6-clearwater.clearwater.test'

                # DNS record found for ralf.site1.md6-clearwater.clearwater.test, so Ralf will be used
                ralf_hostname='ralf.site1.md6-clearwater.clearwater.test:10888'
                ralf_session_store='site1=astaire.site1.md6-clearwater.clearwater.test'
                ralf_chronos_callback_uri='ralf.md6-clearwater.clearwater.test'
                billing_realm='billing.md6-clearwater.clearwater.test'

                # DNS record found for SRV _diameter._tcp.md6-clearwater.clearwater.test, so assuming an external HSS in use
                hss_realm='md6-clearwater.clearwater.test'


                sas_server='sas.md6-clearwater.clearwater.test'

                # DNS record found for snmp-manager.md6-clearwater.clearwater.test, so using SNMP
                #snmp_ip='10.225.167.11'
                # DNS record found for enum.md6-clearwater.clearwater.test
                enum_server='enum.md6-clearwater.clearwater.test'
                snmp_notification_types='enterprise'

                icscf='5052'
                scscf='5054'

                hss_reregistration_time='0'
                reg_max_expires='3600'
                enforce_user_phone='Y'
                enforce_global_only_lookups='Y'

                remote_audit_logging_server="10.225.22.158:514\""""

        config_access.print_diff_and_syslog("shared_config", string1, string2)
        self.assertIs(mock_syslog.call_count, 1)

    @mock.patch("metaswitch.clearwater.config_manager.config_access.sys.stdout",
                new_callable=StringIO)
    def test_duplicate_and_move(self, mock_stdout, mock_getname, mock_syslog, mock_unified_diff):
        """Check that a moved file that is duplicated doesn't cause issues."""
        mock_unified_diff.return_value = False
        mock_getname.return_value = 'name'
        string1 = """Config
                     Line 1
                     Line 2
                     Line 3"""

        string2 = """Config
                     Line 2
                     Line 3
                     Line 1
                     Line 1"""

        answer = config_access.print_diff_and_syslog("shared_config",
                                                     string1,
                                                     string2)
        self.assertIs(answer, True)
        textchanges = """Configuration file change: user name has modified shared_config.
 Lines added:
"                     Line 1"
 Lines moved:
"                     Line 1"
"""
        self.assertMultiLineEqual(mock_stdout.getvalue(), textchanges)

    @mock.patch("metaswitch.clearwater.config_manager.config_access.sys.stdout",
                new_callable=StringIO)
    def test_check_unified_diff(self, mock_stdout, mock_getname, mock_syslog, mock_unified_diff):
        """Check unified diffs."""
        mock_unified_diff.return_value = True
        mock_getname.return_value = 'name'
        string1 = """<xml>
                       <tag1>
                       </tag1>
                       <tag2>
                       </tag2>
                       <tag3>
                         <tag3a>
                         </tag3a>
                       </tag3>
                       <tag4>
                       </tag4>
                       <tag5>
                       </tag5>
                       <tag6>
                       </tag6>
                  """

        string2 = """<xml>
                       <tag1>
                       </tag1>
                       <tag3>
                         <tag3a>
                           <tag3a-i>
                           </tag3a-i>
                           <tag3a-ii>
                           </tag3a-ii>
                         </tag3a>
                         <tag3b>
                         </tag3b>
                       </tag3>
                       <tag4>
                       </tag4>
                       <tag5>
                       </tag5>
                       <tag6>
                       </tag6>
                  """

        answer = config_access.print_diff_and_syslog("xml",
                                                     string1,
                                                     string2)
        self.assertIs(answer, True)
        # Note use of escaped space to prevent editors from removing spaces.
        textchanges = """Configuration file change: user name has modified xml.
 Changes:
---\x20

+++\x20

@@ -1,11 +1,15 @@

 <xml>
                        <tag1>
                        </tag1>
-                       <tag2>
-                       </tag2>
                        <tag3>
                          <tag3a>
+                           <tag3a-i>
+                           </tag3a-i>
+                           <tag3a-ii>
+                           </tag3a-ii>
                          </tag3a>
+                         <tag3b>
+                         </tag3b>
                        </tag3>
                        <tag4>
                        </tag4>
"""
        self.maxDiff = None
        self.assertMultiLineEqual(mock_stdout.getvalue(), textchanges)



