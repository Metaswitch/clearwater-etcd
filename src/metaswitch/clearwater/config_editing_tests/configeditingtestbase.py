# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

import unittest
import mock
import os
import subprocess
from metaswitch.common.logging_config import configure_test_logging

cw_config = __import__("cw-config")

configure_test_logging()


class TestConfigEditing(unittest.TestCase):

#    @mock.patch('clearwater_etcd_plugins.clearwater_queue_manager.apply_config_plugin.os.listdir')
    def atest_validate_config_unforced(self):
#        cw_config.validate_config(False)

#        cw_config.validate_config(False)

        pass


class TestValidation(unittest.TestCase):

    @mock.patch('os.access')
    @mock.patch('subprocess.check_call')
    @mock.patch('os.listdir')
    def test_scripts_run_ok(self, mock_listdir, mock_subprocess, mock_access):
        """Check that we run the validation scripts we find in the relevant
        folder."""

        mock_listdir.return_value = ['scriptA', 'scriptB']
        mock_access.return_value = [True, True]

        cw_config.validate_config(False)
        mock_listdir.assert_called_once_with(cw_config.VALIDATION_SCRIPTS_FOLDER)

        for call_info, script in zip(mock_subprocess.call_args_list,mock_listdir.return_value):
            args = call_info[0]
            assert(script in args[0])

    @mock.patch('os.access')
    @mock.patch('subprocess.check_call')
    @mock.patch('os.listdir')
    def test_only_run_accessible(self, mock_listdir, mock_subprocess, mock_access):
        """Check that we only attempt to run accessible script."""

        mock_listdir.return_value = ['scriptA', 'scriptB']
        mock_access.return_value = [True, False]

        cw_config.validate_config(False)
        mock_listdir.assert_called_once_with(cw_config.VALIDATION_SCRIPTS_FOLDER)

        for call_info, script in zip(mock_subprocess.call_args_list,mock_listdir.return_value):
            args = call_info[0]
            assert(script in args[0])

    @mock.patch('os.access')
    @mock.patch('subprocess.check_call')
    @mock.patch('os.listdir')
    def test_handle_validation_error(self, mock_listdir, mock_subprocess, mock_access):
        """Test that we handle validation failure correctly."""

        mock_listdir.return_value = ['scriptA', 'scriptB']
        mock_access.return_value = [True, True]
        mock_subprocess.side_effect = [None, subprocess.CalledProcessError("A", "B")]


        try:
           cw_config.validate_config(False)
           assertTrue(False)
        except cw_config.ConfigUploadFailed as e:
            pass

        for call_info, script in zip(mock_subprocess.call_args_list,mock_listdir.return_value):
            args = call_info[0]
            assert(script in args[0])

    @mock.patch('os.access')
    @mock.patch('subprocess.check_call')
    @mock.patch('os.listdir')
    def test_ignore_validation_error(self, mock_listdir, mock_subprocess, mock_access):
        """Test that we handle validation failure correctly."""

        mock_listdir.return_value = ['scriptA', 'scriptB']
        mock_access.return_value = [True, True]
        mock_subprocess.side_effect = [None, subprocess.CalledProcessError("A", "B")]

        cw_config.validate_config(True)

        for call_info, script in zip(mock_subprocess.call_args_list,mock_listdir.return_value):
            args = call_info[0]
            assert(script in args[0])



if __name__ == '__main__':
    unittest.main()
