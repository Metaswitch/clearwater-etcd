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
LOG_DIR = "/var/log/clearwater-config-manager"
VALIDATION_SCRIPTS_FOLDER = "/usr/share/clearwater/clearwater-config-manager/scripts/config_validation/"
JSON_GENERIC_UPLOAD = '/usr/share/clearwater/clearwater-config-manager/scripts/validate_json.py'
log = logging.getLogger()


class ConfigType:
    """This is the base class for config type. \n
    All subclasses need the variables: name, filetype and help_info.
    All subclasses with filetype json or xml also need schema for use with
    validation. """
    # name is how the config_type is passed into a list of choices for the arg-
    # parsing.
    # help_info is also used in arg-parsing but to give the user some more
    # information on the config files that are available when -h/--help is
    # called.
    # filetype is used in the __init__ method below to pick which validation
    # scripts to use.
    # schema is used with those config types that require validation to say
    # where the vaildation schema can be found.

    def __init__(self, configpath):
        self.configfile = configpath
        # self.scripts is a list of lists, this is needed because the lists are
        # passed into subprocess.call to run the validation script. They are in
        # a list as multiple validation scripts can be available for a
        # configuration type.
        # The config types can be broken down into categories and depending on
        # which category the validation scripts are a certain style.

        if self.filetype == 'json':
            # This is for dns_json, enum_json, bgcf_json, mmf_targets_json and
            # scscf_json.
            self.scripts, self.script_names = self.get_json_validation()

        elif self.filetype == 'xml':
            # This is for shared_ifcs_xml and fallback_ifcs_xml
            self.scripts, self.script_names = self.get_xml_validation()

        elif self.filetype == 'shared_config':
            # This is for just shared_config
            self.scripts, self.script_names = self.get_sharedconfig_validation()

        else:
            # Currently weatherwax and chronos have no validation scripts
            self.scripts = []
            self.script_names = []

    def __str__(self):
        return self.name

    def get_json_validation(self):
        scripts = [['python', JSON_GENERIC_UPLOAD, self.schema,
                    self.configfile], ]
        # This is used for logging
        script_names = [self.schema, ]
        return scripts, script_names

    def get_xml_validation(self):
        scripts = [['xmllint', '--format', '--pretty', '1', '--load-trace',
                    '--debug', '--schema', '${}'.format(self.schema),
                    '${}'.format(self.configfile)], ]
        # This is used for logging
        script_names = [self.schema, ]
        return scripts, script_names

    def get_sharedconfig_validation(self):
        script_dir = os.listdir(VALIDATION_SCRIPTS_FOLDER)
        # We can only execute scripts that have execute permissions.
        scripts = [os.path.join(VALIDATION_SCRIPTS_FOLDER, s)
                   for s in script_dir
                   if os.access(os.path.join(
                       VALIDATION_SCRIPTS_FOLDER, s), os.X_OK)]
        # script_names is used for logging
        script_names = scripts
        return scripts, script_names

    def validate(self):
        """This method inheritss the scripts to run validation against and then
        runs them all before returning a list of those that have failed"""
        # The scripts to validate against are defined by the __init__ method
        # using one of the get validation methods.

        failed_scripts = []
        i = 0
        for script in self.scripts:
            try:
                log.debug("Running validation script %s", self.script_names[i])
                subprocess.check_output(script, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as exc:
                log.error("Validation script %s failed with output:\n %s",
                          os.path.basename(self.script_names[i]),
                          exc.output)

                # We want to run through all the validation scripts so we can
                # tell the user all of the problems with their config changes,
                # so don't bail out of the loop at this point, just record
                # which scripts have failed.
                failed_scripts.append(self.script_names[i])
            i = i + 1
        return failed_scripts
