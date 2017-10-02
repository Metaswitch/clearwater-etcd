# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import mock
from StringIO import StringIO
import subprocess
import unittest

import etcd.client


import metaswitch.clearwater.config_manager.move_config as move_config


class TestValidation(unittest.TestCase):

    @mock.patch('os.access')
    @mock.patch('subprocess.check_call')
    @mock.patch('os.listdir')
    def test_scripts_run_ok(self, mock_listdir, mock_subprocess, mock_access):
        """Check that we run the validation scripts we find in the relevant
        folder."""

        mock_listdir.return_value = ['scriptA', 'scriptB']
        mock_access.return_value = [True, True]

        move_config.validate_config(False)

        # Make sure we are looking in the right place.
        mock_listdir.assert_called_with(move_config.VALIDATION_SCRIPTS_FOLDER)

        for call_info, script in zip(mock_subprocess.call_args_list,mock_listdir.return_value):
            args = call_info[0]
            self.assertIn(script, args[0])

    @mock.patch('os.access')
    @mock.patch('subprocess.check_call')
    @mock.patch('os.listdir')
    def test_only_run_accessible(self, mock_listdir, mock_subprocess, mock_access):
        """Check that we only attempt to run accessible script."""

        mock_listdir.return_value = ['scriptA', 'scriptB']
        mock_access.return_value = [True, False]

        move_config.validate_config(False)
        mock_listdir.assert_called_once_with(move_config.VALIDATION_SCRIPTS_FOLDER)

        for call_info, script in zip(mock_subprocess.call_args_list,mock_listdir.return_value):
            args = call_info[0]
            self.assertIn(script, args[0])

    @mock.patch('os.access')
    @mock.patch('subprocess.check_call')
    @mock.patch('os.listdir')
    def test_handle_validation_error(self, mock_listdir, mock_subprocess, mock_access):
        """Test that we handle validation failure correctly."""

        mock_listdir.return_value = ['scriptA', 'scriptB']
        mock_access.return_value = [True, True]
        mock_subprocess.side_effect = [None, subprocess.CalledProcessError("A", "B")]

        self.assertRaises(move_config.ConfigValidationFailed, move_config.validate_config, False)

        for call_info, script in zip(mock_subprocess.call_args_list,mock_listdir.return_value):
            args = call_info[0]
            self.assertIn(script, args[0])

    @mock.patch('os.access')
    @mock.patch('subprocess.check_call')
    @mock.patch('os.listdir')
    def test_ignore_validation_error(self, mock_listdir, mock_subprocess, mock_access):
        """Test that we handle validation failure correctly."""

        mock_listdir.return_value = ['scriptA', 'scriptB']
        mock_access.return_value = [True, True]
        mock_subprocess.side_effect = [None, subprocess.CalledProcessError("A", "B")]

        move_config.validate_config(True)

        for call_info, script in zip(mock_subprocess.call_args_list,mock_listdir.return_value):
            args = call_info[0]
            self.assertIn(script, args[0])


class TestConfigLoader(unittest.TestCase):

    def test_uri(self):
        """Check we can get the correct URI for config in etcd."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_client.base_uri = "http://base_uri"
        etcd_client.key_endpoint = "key_endpoint"

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site")

        full_uri = config_loader.full_uri

        self.assertEqual(
            full_uri,
            "http://base_uri/key_endpoint/clearwater/site/configuration")

    def test_get_config(self):
        """Check we use the right URI to download config."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_result = mock.MagicMock()
        etcd_result.value = "Some Config"
        etcd_result.modifiedIndex = 123
        etcd_client.read.return_value = etcd_result

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site")

        config = config_loader.get_config_and_index("shared_config")

        self.assertEqual(config.value, "Some Config")
        self.assertEqual(config.modifiedIndex, 123)
        etcd_client.read.assert_called_with(
            "/clearwater/site/configuration/shared_config")

    def test_get_config_failed(self):
        """Check we get the right exception on failure."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_client.read.side_effect = etcd.EtcdKeyNotFound

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site")

        self.assertRaises(move_config.ConfigDownloadFailed,
                          config_loader.get_config_and_index,
                          "shared_config")

    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name",
                return_value="ubuntu")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.getenv",
                return_value="/home/ubuntu")
    def test_download_config(self, mock_getenv, mock_user):
        """Check that we can write config from etcd to file."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_result = mock.MagicMock()
        etcd_result.value = "Some Config"
        etcd_result.modifiedIndex = 123
        etcd_client.read.return_value = etcd_result

        mock_config_file = mock.MagicMock()
        mock_index_file = mock.MagicMock()
        mock_config_file.__enter__.return_value = mock_config_file
        mock_index_file.__enter__.return_value = mock_index_file

        def fake_open(file, mode):
            if file == "/home/ubuntu/clearwater-config-manager/staging/ubuntu/shared_config":
                return mock_config_file
            if file == "/home/ubuntu/clearwater-config-manager/staging/ubuntu/shared_config.index":
                return mock_index_file
            else:
                self.fail("Incorrect File Accessed: {}".format(file))

        mock_open = mock.MagicMock(side_effect=fake_open)

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site")

        with mock.patch("metaswitch.clearwater.config_manager.move_config.open", mock_open):
            config_loader.download_config("shared_config")

        mock_config_file.write.assert_called_with("Some Config")
        mock_index_file.write.assert_called_with("123")

        calls = [
            mock.call("/home/ubuntu/clearwater-config-manager/staging/ubuntu/shared_config", "w"),
            mock.call("/home/ubuntu/clearwater-config-manager/staging/ubuntu/shared_config.index", "w"),
        ]
        mock_open.assert_has_calls(calls)

    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name",
                return_value="ubuntu")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.getenv",
                return_value="/home/ubuntu")
    def test_download_no_config_file(self, mock_getenv, mock_user):
        """Check for the correct exception on failure.

        Check that failing to open the config file causes the correct
        exception to be raised."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_result = mock.MagicMock()
        etcd_result.value = "Some Config"
        etcd_result.modifiedIndex = 123
        etcd_client.read.return_value = etcd_result

        def fake_open(file, mode):
            if file == "/home/ubuntu/clearwater-config-manager/staging/ubuntu/shared_config":
                raise IOError
            else:
                self.fail("Incorrect File Accessed: {}".format(file))

        mock_open = mock.MagicMock(side_effect=fake_open)

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site")

        with mock.patch("metaswitch.clearwater.config_manager.move_config.open", mock_open):
            self.assertRaises(
                move_config.ConfigDownloadFailed,
                config_loader.download_config,
                "shared_config")

    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name",
                return_value="ubuntu")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.getenv",
                return_value="/home/ubuntu")
    def test_download_no_index_file(self, mock_getenv, mock_user):
        """Check for the correct exception on failure.

        Check that failing to open the index file causes the correct
        exception to be raised."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_result = mock.MagicMock()
        etcd_result.value = "Some Config"
        etcd_result.modifiedIndex = 123
        etcd_client.read.return_value = etcd_result

        def fake_open(file, mode):
            if file == "/home/ubuntu/clearwater-config-manager/staging/ubuntu/shared_config":
                return mock.MagicMock()
            if file == "/home/ubuntu/clearwater-config-manager/staging/ubuntu/shared_config.index":
                raise IOError
            else:
                self.fail("Incorrect File Accessed: {}".format(file))

        mock_open = mock.MagicMock(side_effect=fake_open)

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site")

        with mock.patch("metaswitch.clearwater.config_manager.move_config.open", mock_open):
            self.assertRaises(
                move_config.ConfigDownloadFailed,
                config_loader.download_config,
                "shared_config")

    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name",
                return_value="ubuntu")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.getenv",
                return_value="/home/ubuntu")
    def test_upload_config(self, mock_getenv, mock_user):
        """Check that we can write config to etcd from file."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)

        mock_config_file = mock.MagicMock()
        mock_config_file.__enter__.return_value = mock_config_file
        mock_config_file.read.return_value = "Fake Config"

        def fake_open(file, mode):
            if file == "/home/ubuntu/clearwater-config-manager/staging/ubuntu/shared_config":
                return mock_config_file
            else:
                self.fail("Incorrect File Accessed: {}".format(file))

        mock_open = mock.MagicMock(side_effect=fake_open)

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site")

        with mock.patch("metaswitch.clearwater.config_manager.move_config.open", mock_open):
            # Need to provide a cas revision on etcd uploads to
            # avoid conflicts.
            config_loader.upload_config("shared_config", 123)

        etcd_client.write.assert_called_with(
            "/clearwater/site/configuration/shared_config",
            "Fake Config",
            prevIndex=123
        )

    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name",
                return_value="ubuntu")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.getenv",
                return_value="/home/ubuntu")
    def test_upload_no_config_file(self, mock_getenv, mock_user):
        """Check for the correct exception on failure.

        Check that failing to open the config file causes the correct
        exception to be raised."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)

        def fake_open(file, mode):
            if file == "/home/ubuntu/clearwater-config-manager/staging/ubuntu/shared_config":
                raise IOError
            else:
                self.fail("Incorrect File Accessed: {}".format(file))

        mock_open = mock.MagicMock(side_effect=fake_open)

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site")

        with mock.patch("metaswitch.clearwater.config_manager.move_config.open", mock_open):
            self.assertRaises(
                move_config.ConfigUploadFailed,
                config_loader.upload_config,
                "shared_config",
                123)

    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name",
                return_value="ubuntu")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.getenv",
                return_value="/home/ubuntu")
    def test_upload_no_connection(self, mock_getenv, mock_user):
        """Check for the correct exception on failure.

        Check that failing to connect to etcd causes the correct
        exception to be raised."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_client.write.side_effect = etcd.EtcdConnectionFailed

        mock_config_file = mock.MagicMock()
        mock_config_file.read.return_value = "Fake Config"

        def fake_open(file, mode):
            if file == "/home/ubuntu/clearwater-config-manager/staging/ubuntu/shared_config":
                return mock_config_file
            else:
                self.fail("Incorrect File Accessed: {}".format(file))

        mock_open = mock.MagicMock(side_effect=fake_open)

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site")

        with mock.patch("metaswitch.clearwater.config_manager.move_config.open", mock_open):
            self.assertRaises(
                move_config.ConfigUploadFailed,
                config_loader.upload_config,
                "shared_config",
                1234)

    @mock.patch('confirm_process.raw_input')
    def test_yes(self, mock_raw_input):
        mock_raw_input.return_value = 'yes'
        answer = move_config.confirm_yn('Test 1 ', False)
        self.assertIs(answer, True)

    @mock.patch('confirm_process.raw_input')
    def test_no(self, mock_raw_input):
        mock_raw_input.return_value = 'no'
        answer = move_config.confirm_yn('Test 2 ', False)
        self.assertIs(answer, False)

    @mock.patch('confirm_process.raw_input')
    def test_skip(self, mock_raw_input):
        mock_raw_input.return_value = 'no'
        answer = move_config.confirm_yn('Test 3 ', True)
        self.assertIs(answer, True)

    @mock.patch('confirm_process.raw_input')
    def test_upper_yes(self, mock_raw_input):
        mock_raw_input.return_value = 'YeS'
        answer = move_config.confirm_yn('Test 4 ', False)
        self.assertIs(answer, True)

    @mock.patch('confirm_process.raw_input')
    def test_upper_no(self, mock_raw_input):
        mock_raw_input.return_value = 'nO'
        answer = move_config.confirm_yn('Test 5 ', False)
        self.assertIs(answer, False)

    @mock.patch('confirm_process.raw_input')
    def test_wrong_in1(self, mock_raw_input):
        mock_raw_input.side_effect = ['noo', 'yese', '1', '2e', 'y', 'notneed']
        answer = move_config.confirm_yn('Test 6 ', False)
        self.assertEqual(mock_raw_input.call_count, 5)
        self.assertIs(answer, True)

    @mock.patch('confirm_process.raw_input')
    def test_wrong_in2(self, mock_raw_input):
        mock_raw_input.side_effect = ['AS', '1WY1', 'Y3s', 'fo{}', '[]2e', 'n']
        answer = move_config.confirm_yn('Test 7 ', False)
        self.assertEqual(mock_raw_input.call_count, 6)
        self.assertIs(answer, False)
