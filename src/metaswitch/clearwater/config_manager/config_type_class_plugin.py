#!/usr/share/clearwater/clearwater-config-manager/env/bin/python
# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

"""This file contains the Base class for all of the config types"""
import subprocess
import os
import logging
import glob
LOG_DIR = "/var/log/clearwater-config-manager"
VALIDATION_SCRIPTS_FOLDER = "/usr/share/clearwater/clearwater-config-manager/scripts/config_validation/"
JSON_GENERIC_VALIDATE = '/usr/share/clearwater/clearwater-config-manager/scripts/validate_json.py'
log = logging.getLogger("cw-config.validate")


class ConfigType:
    """
    This is the base class for config type.
    All subclasses need the variables: name, filetype and help_info. All
    subclasses with filetype json or xml also need schema for use with
    validation.

    name - Users will reference the config type as this on the command line,
    eg. `cw-config download [name]` It is the name of the config file in
    clearwater-etcdctl and is used for this purpose too.

    help_info - Appears as user-visible help text in the usage statement for
    cw-config.

    filetype - Used to pick which validation scripts to use. Different
    config_types take different inputs to being called for validation.

    file_download_name - Used to agree with the current naming system when
    writing to file.

    schema - Used with those config types that require validation to say
    where the vaildation schema can be found.
    """

    def __init__(self, configpath):
        """
        self.scripts - A list of lists, this is needed because the lists are
        passed into subprocess.call to run the validation script. They are in
        a list as multiple validation scripts can be available for a
        configuration type.
        The config types can be broken down into categories and depending on
        which category the validation scripts are a certain style.
        self.configfile - The path to the config file to be validated.
        """
        self.configfile = configpath

        if self.filetype == 'json':
            self.scripts = self.get_json_validation()

        elif self.filetype == 'xml':
            self.scripts = self.get_xml_validation()

        elif self.filetype == 'shared_config':
            self.scripts = self.get_sharedconfig_validation()

        else:
            # Currently weatherwax has no validation scripts
            self.scripts = {}

    def __str__(self):
        """If the class is asked to be printed it's name is printed."""
        return self.name

    def get_json_validation(self):
        """Returns the scripts to be used for json file validation."""
        scripts = {}
        scripts[self.schema] = ['python', JSON_GENERIC_VALIDATE, self.schema,
                                self.configfile]
        # to add more validation scripts add to the dict of scripts
        return scripts

    def get_xml_validation(self):
        """Returns the scripts to be used for xml file validation."""
        scripts = {}
        scripts[self.schema] = ['xmllint', '--format', '--pretty', '1',
                                '--debug', '--schema',
                                '{}'.format(self.schema),
                                '{}'.format(self.configfile)]
        # to add more validation scripts add to the dict of scripts
        return scripts

    def get_sharedconfig_validation(self):
        """Returns the scripts to be used for shared config file validation."""
        script_dir = glob.glob(os.path.join(VALIDATION_SCRIPTS_FOLDER, '*'))
        # We can only execute scripts that have execute permissions.:q
        scripts = {script: [script, self.configfile]
                   for script in script_dir
                   if os.access(script, os.X_OK)}
        return scripts

    def use_unified_diff(self):
        """Returns true if diffs should be in unified diff format or false
        if per-line."""
        unified_diff = self.filetype in ['json', 'xml']
        return unified_diff

    # This validation method was found to be too restrictive, and custom
    # __init__ and validate() functions had to be written for RphJson.
    # Editing this class to be less restrictive and changing RphJson to use
    # this class's functions has been left as technical debt.
    def validate(self):
        """
        This method inherits the scripts to run validation against and then
        runs them all. To run them the scripts must be able to be passed into
        subprocess.check_output().
        Then returning a list of those that have failed.
        """

        failed_scripts = []
        error_lines = []
        for script in self.scripts:
            try:
                log.debug("Running validation script %s", script)
                subprocess.check_output(self.scripts[script], stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as exc:
                log.error("Validation script %s failed", os.path.basename(script))
                log.error("Reasons for failure:")

                errors = exc.output.splitlines()
                error_lines.extend(errors)

                for line in errors:
                    log.error(line)

                # We want to run through all the validation scripts so we can
                # tell the user all of the problems with their config changes,
                # so don't bail out of the loop at this point, just record
                # which scripts have failed. If any scripts have failed an
                # exception is raised from the return value
                failed_scripts.append(script)
        return failed_scripts, error_lines
