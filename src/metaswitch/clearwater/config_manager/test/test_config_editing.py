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

import etcd.client

import metaswitch.clearwater.config_manager.move_config as move_config

class TestConfigLoader(unittest.TestCase):
    @mock.patch("metaswitch.clearwater.config_manager.move_config.subprocess.check_call",
               side_effect=subprocess.CalledProcessError(101, "fake"))
    def test_check_connection_exception(self, mock_subprocess_check_call):
        """Check that we raise a subprocess.CalledProcessError exception if the
        etcd process is not running."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_client.host = "host"
        etcd_client.port = "0000"

        mock_localstore = mock.MagicMock(spec=move_config.LocalStore)
        with self.assertRaises(move_config.EtcdConnectionFailed):
            move_config.ConfigLoader(etcd_client,
                                     "clearwater",
                                     "site",
                                     mock_localstore)

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader._check_connection")
    def test_download_unable_to_save(self, mock_check_connection):
        """Check for the correct exception on failure.

        Check that failing to save the config/index file causes the correct
        exception to be raised."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        mock_localstore = mock.MagicMock(spec=move_config.LocalStore)
        mock_localstore.save_config_and_revision.side_effect = IOError

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site", mock_localstore)

        self.assertRaises(
            move_config.ConfigDownloadFailed,
            config_loader.download_config,
            "shared_config")

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader._check_connection")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name",
                return_value="ubuntu")
    def test_get_config(self, mock_user, mock_check_connection):
        """Check we use the right URI to download config."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_result = mock.MagicMock()
        etcd_result.value = "Some Config"
        etcd_result.modifiedIndex = 123
        etcd_client.read.return_value = etcd_result

        mock_localstore = mock.MagicMock(spec=move_config.LocalStore)

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site", mock_localstore)

        config, index = config_loader.get_config_and_index("shared_config")

        self.assertEqual(config, "Some Config")
        self.assertEqual(index, 123)
        etcd_client.read.assert_called_with(
            "/clearwater/site/configuration/shared_config")

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader._check_connection")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name",
                return_value="ubuntu")
    def test_get_config_failed(self, mock_user, mock_check_connection):
        """Check we get the right exception on failure."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_client.read.side_effect = etcd.EtcdKeyNotFound

        mock_localstore = mock.MagicMock(spec=move_config.LocalStore)

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site", mock_localstore)

        self.assertRaises(move_config.ConfigDownloadFailed,
                          config_loader.get_config_and_index,
                          "shared_config")

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader._check_connection")
    def test_write_config_to_etcd(self, mock_check_connection):
        """Check that we can write config to etcd from file."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        mock_localstore = mock.MagicMock(spec=move_config.LocalStore)
        mock_localstore.load_config_and_revision.return_value = ("Fake Config", 1000)

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site", mock_localstore)

        # Need to provide a cas revision on etcd uploads to avoid conflicts.
        config_loader.write_config_to_etcd("shared_config", 123)

        etcd_client.write.assert_called_with(
            "/clearwater/site/configuration/shared_config",
            "Fake Config",
            prevIndex=123
        )

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader._check_connection")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name",
                return_value="ubuntu")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.getenv",
                return_value="/home/ubuntu")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.makedirs")
    def test_write_to_etcd_unable_to_load(self, mock_mkdir, mock_getenv, mock_user, mock_check_connection):
        """Check for the correct exception on failure.

        Check that failing to open the config file causes the correct
        exception to be raised."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)

        mock_localstore = mock.MagicMock(spec=move_config.LocalStore)
        mock_localstore.load_config_and_revision.side_effect = IOError

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site", mock_localstore)

        self.assertRaises(
            move_config.ConfigUploadFailed,
            config_loader.write_config_to_etcd,
            "shared_config",
            123)

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader._check_connection")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name",
                return_value="ubuntu")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.getenv",
                return_value="/home/ubuntu")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.makedirs")
    def test_write_to_etcd_no_connection(self, mock_mkdir, mock_getenv, mock_user, mock_check_connection):
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
        mock_localstore = mock.MagicMock(spec=move_config.LocalStore)
        mock_localstore.load_config_and_revision.return_value = ("Local Config", 100)

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site", mock_localstore)

        with mock.patch("metaswitch.clearwater.config_manager.move_config.open", mock_open):
            self.assertRaises(
                move_config.ConfigUploadFailed,
                config_loader.write_config_to_etcd,
                "shared_config",
                1234)

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader._check_connection")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name",
                return_value="ubuntu")
    def test_uri(self, mock_user, mock_check_connection):
        """Check we can get the correct URI for config in etcd."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)
        etcd_client.base_uri = "http://base_uri"
        etcd_client.key_endpoint = "key_endpoint"

        mock_localstore = mock.MagicMock(spec=move_config.LocalStore)

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site", mock_localstore)

        full_uri = config_loader.full_uri

        self.assertEqual(
            full_uri,
            "http://base_uri/key_endpoint/clearwater/site/configuration")


class TestLocalStore(unittest.TestCase):
    # TODO: adjust to LocalStore, test ensure_directory
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader._check_connection")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name",
                return_value="ubuntu")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.path.exists",
                return_value=True)
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.makedirs")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.open")
    def test_folder_exists(self, mock_open, mock_mkdir, mock_exists, mock_user, mock_check_connection):
        """Make sure that we don't try to create a folder if one already
        exists."""
        etcd_client = mock.MagicMock(spec=etcd.client.Client)

        mock_localstore = mock.MagicMock(spec=move_config.LocalStore)

        config_loader = move_config.ConfigLoader(
            etcd_client, "clearwater", "site", mock_localstore)

        config_loader.download_config("shared_config")

        # Make sure we haven't tried to create a dir when one exists.
        self.assertEqual(mock_mkdir.call_count, 0)

    # TODO
    def test_no_config_to_load(self):
        """Test that we raise the right exception if there is no config file to
        load."""
        pass

    # TODO
    def test_no_index_to_load(self):
        """Test that we raise the right exception if there is no index file to
        load."""
        pass

    # TODO
    def test_load_non_integer(self):
        """Test that we raise the right exception if we try to load a
        non-integer"""
        pass

    # TODO
    def test_unable_to_save_file(self):
        """Test that we raise the right exception if we are unable to save the
        config or index file."""
        pass


class TestYesNo(unittest.TestCase):
    @mock.patch('metaswitch.clearwater.config_manager.move_config.raw_input')
    def test_yes(self, mock_raw_input):
        """tests a yes input to the confirm function returns true"""
        mock_raw_input.return_value = 'yes'
        answer = move_config.confirm_yn('Test 1 ', False)
        self.assertIs(answer, True)

    @mock.patch('metaswitch.clearwater.config_manager.move_config.raw_input')
    def test_no(self, mock_raw_input):
        """tests a no input to the confirm function returns false"""
        mock_raw_input.return_value = 'no'
        answer = move_config.confirm_yn('Test 2 ', False)
        self.assertIs(answer, False)

    @mock.patch('metaswitch.clearwater.config_manager.move_config.raw_input')
    def test_skip(self, mock_raw_input):
        """checks that inputting autoskip as
         true returns true even with a no input"""
        mock_raw_input.return_value = 'no'
        answer = move_config.confirm_yn('Test 3 ', True)
        self.assertIs(answer, True)

    @mock.patch('metaswitch.clearwater.config_manager.move_config.raw_input')
    def test_upper_yes(self, mock_raw_input):
        """Checks the yes input can have upper case"""
        mock_raw_input.return_value = 'YeS'
        answer = move_config.confirm_yn('Test 4 ', False)
        self.assertIs(answer, True)

    @mock.patch('metaswitch.clearwater.config_manager.move_config.raw_input')
    def test_upper_no(self, mock_raw_input):
        """checks the no input can have upper case"""
        mock_raw_input.return_value = 'nO'
        answer = move_config.confirm_yn('Test 5 ', False)
        self.assertIs(answer, False)

    @mock.patch('metaswitch.clearwater.config_manager.move_config.raw_input')
    def test_wrong_in1(self, mock_raw_input):
        """checks the function asks for further inputs until a correct
        response is supplied, also checks that 'y' is acceptable"""
        mock_raw_input.side_effect = ['noo', 'yese', '1', '2e', 'y', 'notneed']
        answer = move_config.confirm_yn('Test 6 ', False)
        self.assertEqual(mock_raw_input.call_count, 5)
        self.assertIs(answer, True)

    @mock.patch('metaswitch.clearwater.config_manager.move_config.raw_input')
    def test_wrong_in2(self, mock_raw_input):
        """A second check for checking the function asks for correct responses
        until one is supplied, also checks that 'n' is accpetable"""
        mock_raw_input.side_effect = ['AS', '1WY1', 'Y3s', 'fo{}', '[]2e', 'n']
        answer = move_config.confirm_yn('Test 7 ', False)
        self.assertEqual(mock_raw_input.call_count, 6)
        self.assertIs(answer, False)


class TestMain(unittest.TestCase):
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.configure_logging")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader")
    @mock.patch("metaswitch.clearwater.config_manager."
                "move_config.delete_outdated_config_files")
    def test_delete_outdated_config_files(self,
                                          mock_delete_files,
                                          mock_configloader,
                                          mock_logging):
        """Make sure we always call delete_outdated_config_files"""
        args = mock.Mock()
        move_config.main(args)

        mock_delete_files.assert_called_with()

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.configure_logging")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.download_config")
    def test_download_action_main_line(self,
                                       mock_download_config,
                                       mock_configloader,
                                       mock_logging):
        """Make sure that we always call download_config in download mode."""
        args = mock.Mock(action='download')
        move_config.main(args)

        assert mock_download_config.called

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.configure_logging")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.download_config")
    def test_handle_download_configdownloadfailed(self,
                                                  mock_download_config,
                                                  mock_configloader,
                                                  mock_logging):
        """Check that we handle a ConfigDownloadFailed exception raised by
        download_config."""
        mock_download_config.side_effect = move_config.ConfigDownloadFailed
        args = mock.Mock(action='download')

        with self.assertRaises(SystemExit):
            move_config.main(args)

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.configure_logging")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.download_config")
    def test_handle_download_ioerror(self,
                                     mock_download_config,
                                     mock_configloader,
                                     mock_logging):
        """Check that we handle an IOError exception raised by
        download_config."""
        mock_download_config.side_effect = IOError
        args = mock.Mock(action='download')

        with self.assertRaises(SystemExit):
            move_config.main(args)

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.configure_logging")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.download_config")
    def test_handle_download_userabort(self,
                                       mock_download_config,
                                       mock_configloader,
                                       mock_logging):
        """Check that we handle a UserAbort exception raised by
        download_config."""
        mock_download_config.side_effect = move_config.UserAbort
        args = mock.Mock(action='download')

        with self.assertRaises(SystemExit):
            move_config.main(args)

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.configure_logging")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.ConfigLoader")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.upload_verified_config")
    def test_upload_action_main_line(self,
                                     mock_upload_config,
                                     mock_configloader,
                                     mock_logging):
        """Make sure that we always call upload_verified_config in upload mode."""
        args = mock.Mock(action='upload')
        move_config.main(args)

        assert mock_upload_config.called

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.configure_logging")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.upload_verified_config")
    def test_handle_upload_etcdmasterconfigchanged(self,
                                                   mock_upload_config,
                                                   mock_configloader,
                                                   mock_logging):
        """Check that we handle a EtcdMasterConfigChanged exception raised by
        upload_verified_config."""
        mock_upload_config.side_effect = move_config.EtcdMasterConfigChanged
        args = mock.Mock(action='upload')

        with self.assertRaises(SystemExit):
            move_config.main(args)

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.configure_logging")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.upload_verified_config")
    def test_handle_upload_configuploadfailed(self,
                                              mock_upload_config,
                                              mock_configloader,
                                              mock_logging):
        """Check that we handle a ConfigUploadFailed exception raised by
        upload_verified_config."""
        mock_upload_config.side_effect = move_config.ConfigUploadFailed
        args = mock.Mock(action='upload')

        with self.assertRaises(SystemExit):
            move_config.main(args)

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.configure_logging")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.upload_verified_config")
    def test_handle_upload_configvalidationfailed(self,
                                                  mock_upload_config,
                                                  mock_configloader,
                                                  mock_logging):
        """Check that we handle a ConfigValidationFailed exception raised by
        upload_verified_config."""
        mock_upload_config.side_effect = move_config.ConfigValidationFailed
        args = mock.Mock(action='upload')

        with self.assertRaises(SystemExit):
            move_config.main(args)

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.configure_logging")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.upload_verified_config")
    def test_handle_upload_ioerror(self,
                                   mock_upload_config,
                                   mock_configloader,
                                   mock_logging):
        """Check that we handle an IOError exception raised by
        upload_verified_config."""
        mock_upload_config.side_effect = IOError
        args = mock.Mock(action='upload')

        with self.assertRaises(SystemExit):
            move_config.main(args)

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.configure_logging")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.upload_verified_config")
    def test_handle_upload_userabort(self,
                                     mock_upload_config,
                                     mock_configloader,
                                     mock_logging):
        """Check that we handle a UserAbort exception raised by
        upload_verified_config."""
        mock_upload_config.side_effect = move_config.UserAbort
        args = mock.Mock(action='upload')

        with self.assertRaises(SystemExit):
            move_config.main(args)

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.configure_logging")
    @mock.patch("etcd.client.Client")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.upload_verified_config")
    def test_handle_etcdexception(self,
                                  mock_upload_config,
                                  mock_etcd_client,
                                  mock_logging):
        """Check that we handle an EtcdException raised by
        etcd.client.Client."""
        mock_etcd_client.side_effect = etcd.EtcdException
        args = mock.Mock(action='upload')

        with self.assertRaises(SystemExit):
            move_config.main(args)


class TestDownload(unittest.TestCase):
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.confirm_yn")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.os.path.exists")
    def test_confirm_overwrite(self, mock_path_exists, mock_confirm_yn):
        """Check that we ask the user for confirmation before overwriting an
        existing file."""
        mock_path_exists.return_value = True
        move_config.download_config(mock.Mock(), mock.Mock(), mock.Mock())

        assert mock_confirm_yn.called

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.confirm_yn")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.os.path.exists")
    def test_deny_overwrite(self, mock_path_exists, mock_confirm_yn):
        """Check that we raise a UserAbort exception if the user denies to
        overwrite an existing file."""
        mock_path_exists.return_value = True
        mock_confirm_yn.return_value = False

        with self.assertRaises(move_config.UserAbort):
            move_config.download_config(mock.Mock(), mock.Mock(), mock.Mock())

    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.ConfigLoader", spec=True)
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.confirm_yn")
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.os.path.exists")
    def test_allow_overwrite(self, mock_path_exists, mock_confirm_yn, mock_configloader):
        """Check that we don't raise a UserAbort exception if the user allows
        to overwrite an existing file and check that we download_config."""
        # mock_path_exists.return_value = True
        # mock_confirm_yn.return_value = True
        #
        # move_config.download_config(mock.Mock(), mock.Mock(), mock.Mock())
        #
        # assert mock_configloader.download_config.called_with("lalala")
        pass


class TestVerifiedUpload(unittest.TestCase):
    @mock.patch(
        "metaswitch.clearwater.config_manager.move_config.validate_config")
    def test_only_upload_validated_config(self, mock_validate_config):
        """Check that we only call upload_config if validation passed."""
        mock_validate_config.side_effect = move_config.ConfigValidationFailed

        mock_upload_config = mock.MagicMock(spec=move_config.upload_config)
        assert not mock_upload_config.called


class TestValidation(unittest.TestCase):

    @mock.patch('os.access')
    @mock.patch('subprocess.check_output')
    @mock.patch('os.listdir')
    def test_scripts_run_ok(self, mock_listdir, mock_subprocess, mock_access):
        """Check that we run the validation scripts we find in the relevant
        folder."""

        mock_listdir.return_value = ['scriptA', 'scriptB']
        mock_access.return_value = [True, True]

        move_config.validate_config(False)

        # Make sure we are looking in the right place.
        mock_listdir.assert_called_with(move_config.VALIDATION_SCRIPTS_FOLDER)

        for call_info, script in zip(mock_subprocess.call_args_list,
                                     mock_listdir.return_value):
            args = call_info[0]
            self.assertIn(script, args[0])

    @mock.patch('os.access')
    @mock.patch('subprocess.check_output')
    @mock.patch('os.listdir')
    def test_only_run_accessible(self,
                                 mock_listdir,
                                 mock_subprocess,
                                 mock_access):
        """Check that we only attempt to run accessible script."""

        mock_listdir.return_value = ['scriptA', 'scriptB']
        mock_access.return_value = [True, False]

        move_config.validate_config(False)
        mock_listdir.assert_called_once_with(
            move_config.VALIDATION_SCRIPTS_FOLDER)

        for call_info, script in zip(mock_subprocess.call_args_list,
                                     mock_listdir.return_value):
            args = call_info[0]
            self.assertIn(script, args[0])

    @mock.patch('os.access')
    @mock.patch('subprocess.check_output')
    @mock.patch('os.listdir')
    def test_handle_validation_error(self,
                                     mock_listdir,
                                     mock_subprocess,
                                     mock_access):
        """Test that we handle validation failure correctly."""

        mock_listdir.return_value = ['scriptA', 'scriptB']
        mock_access.return_value = [True, True]
        mock_subprocess.side_effect = [None,
                                       subprocess.CalledProcessError("A", "B")]

        self.assertRaises(move_config.ConfigValidationFailed,
                          move_config.validate_config,
                          False)

        for call_info, script in zip(mock_subprocess.call_args_list,
                                     mock_listdir.return_value):
            args = call_info[0]
            self.assertIn(script, args[0])

    @mock.patch('os.access')
    @mock.patch('subprocess.check_output')
    @mock.patch('os.listdir')
    def test_ignore_validation_error(self,
                                     mock_listdir,
                                     mock_subprocess,
                                     mock_access):
        """Test that we handle validation failure correctly."""

        mock_listdir.return_value = ['scriptA', 'scriptB']
        mock_access.return_value = [True, True]
        mock_subprocess.side_effect = [None,
                                       subprocess.CalledProcessError("A", "B")]

        move_config.validate_config(True)

        for call_info, script in zip(mock_subprocess.call_args_list,
                                     mock_listdir.return_value):
            args = call_info[0]
            self.assertIn(script, args[0])


class TestUpload(unittest.TestCase):
    def test_different_revision_numbers(self):
        """Check that we raise an EtcdMasterConfigChanged exception if the
        local revision is not the same as the remote revision."""
        pass

    def test_print_diff(self):
        """Check that we always call print_diff_and_syslog."""
        pass

    def test_ask_confirmation(self):
        """Check that we always ask for user confirmation if autoconfirm is
        false."""
        pass

    def test_user_abort(self):
        """Check that we raise a UserAbort exception if autoconfirm is false
        and the user denied to continue."""
        pass

    def test_upload_config(self):
        """Check that we call config_loader.write_config_to_etcd."""
        pass

    def test_remove_file_on_success(self):
        """Check that we remove the local config file on successful upload."""
        pass


class TestDeleteOutdated(unittest.TestCase):
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.remove")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.path.getmtime")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.walk")
    def test_no_delete(self, mock_walk, mock_getmtime, mock_remove):
        """This tests that a recent file is not deleted"""
        # gives time of file creation as 28 days ago
        mock_getmtime.return_value = (time.time() - (28*24*60*60))
        mock_walk.return_value = (('/imaginary_file_name', [], ['testdel.py']),('/imaginary_file_2',[],[]))
        answer = move_config.delete_outdated_config_files()
        # then need to check os.remove is NOT called
        self.assertIs(mock_remove.call_count, 0)

    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.remove")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.path.getmtime")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.walk")
    def test_yes_delete(self, mock_walk, mock_getmtime, mock_remove):
        """This tests that a older file is deleted"""
        # gives the creation time of the file at 32 days
        mock_getmtime.return_value = (time.time() - (32*24*60*60))
        mock_walk.return_value = (('/imaginary_file_name', ['imaginary_file_2'], ['testdel.py']),('/imaginary_file_name/imaginary_file_2',[],[]))
        answer = move_config.delete_outdated_config_files()
        # then need to check os.remove IS called
        self.assertIs(mock_remove.call_count, 1)


class TestUserName(unittest.TestCase):
    @mock.patch("metaswitch.clearwater.config_manager.move_config.subprocess.check_output")
    def test_call_subprocess(self, mock_subp):
        """check that we call subprocess.popen"""
        mock_subp.return_value = ('clearwater fdbngh fghj')
        answer = move_config.get_user_name()
        self.assertIs(mock_subp.call_count, 1)
        self.assertMultiLineEqual(answer, 'clearwater')


class TestUserDownloadDir(unittest.TestCase):
    # """Returns the user-specific directory for downloaded config."""
    # return os.path.join(get_base_download_dir(), get_user_name())
    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_base_download_dir")
    def test_call_get_base(self, mock_getbase, mock_getuser):
        """check that we call get_base_download_dir and get_user_name """
        answer = move_config.get_user_download_dir()
        self.assertIs(mock_getbase.call_count, 1)
        self.assertIs(mock_getuser.call_count, 1)


class TestBaseDownloadDir(unittest.TestCase):
    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.getenv")
    def test_call_osgetenv(self, mock_getenv):
        """check that we call os.getenv(HOME)"""
        answer = move_config.get_base_download_dir()
        self.assertIs(mock_getenv.call_count, 1)

    @mock.patch("metaswitch.clearwater.config_manager.move_config.os.getenv")
    def test_get_runtime_error(self, mock_getenv):
        """check that a runtime error is raised when home is none"""
        mock_getenv.return_value = None
        with self.assertRaises(RuntimeError):
            answer = move_config.get_base_download_dir()


class TestDiffAndSyslog(unittest.TestCase):
    @mock.patch("metaswitch.clearwater.config_manager.move_config.syslog")
    def test_check_iden(self, mock_syslog):
        """check that the diff for two identical files returns false"""
        answer = move_config.print_diff_and_syslog('string is a string \n yay',
                                                   'string is a string \n yay')
        self.assertIs(answer, False)

    from StringIO import StringIO
    @mock.patch("metaswitch.clearwater.config_manager.move_config.syslog")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.sys.stdout", new_callable=StringIO)
    def test_check_diff(self, mock_stdout, mock_getname, mock_syslog):
        """check that for two different files with additions and deletions the
        syslog_str and output_str contain them.
        Also checks that it returns true"""
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

                remote_audit_logging_srver="10.225.22.158:514\""""

        answer = move_config.print_diff_and_syslog(string1, string2)
        self.assertIs(answer, True)
        textchanges = """Configuration file change: shared_config was modified by user name.
 Lines removed:
"                #snmp_ip='10.225.166.11'"
"                remote_audit_logging_server="10.225.22.158:514""
"                site_names='site1'"
 Lines added:
"                #snmp_ip='10.225.167.11'"
"                remote_audit_logging_srver="10.225.22.158:514""
"                site_names='site2'\"\n"""
        self.assertMultiLineEqual(mock_stdout.getvalue(), textchanges)

    @mock.patch("metaswitch.clearwater.config_manager.move_config.syslog")
    @mock.patch("metaswitch.clearwater.config_manager.move_config.get_user_name")
    def test_call_syslog(self, mock_getname, mock_syslog):
        """check that syslog.openlog, syslog.syslog and syslog.closelog are
        called"""
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

        answer = move_config.print_diff_and_syslog(string1, string2)
        self.assertIs(mock_syslog.openlog.call_count, 1)
        self.assertIs(mock_syslog.syslog.call_count, 1)
        self.assertIs(mock_syslog.closelog.call_count, 1)
