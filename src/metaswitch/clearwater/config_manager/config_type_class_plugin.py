"""This file contains the Base class for all of the config types"""
import subprocess
import os
import logging
LOG_DIR = "/var/log/clearwater-config-manager"
VALIDATION_SCRIPTS_FOLDER = "/usr/share/clearwater/clearwater-config-manager/scripts/config_validation/"

log = logging.getLogger("cw-config.main")


class ConfigType:
    """This is the base class for config type"""
    def validate(self):
        # run scripts
            # run each script as validation
        failed_scripts = []
        for script in self.scripts:
            try:
                log.debug("Running validation script %s", script)
                subprocess.check_output(script, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as exc:
                log.error("Validation script %s failed with output:\n %s",
                          os.path.basename(script),
                          exc.output)

            # We want to run through all the validation scripts so we can tell
            # the user all of the problems with their config changes, so don't
            # bail out of the loop at this point, just record which scripts
            # have failed.
                failed_scripts.append(script)

        return failed_scripts

    def __str__(self):
        return self.name

    def get_json_validation(self):
        scripts = [['python', self.call_general, self.schema,
                    self.configfile], ]
        return scripts

    def get_xml_validation(self):
        scripts = [['xmllint', '--format', '--pretty', '1', '--load-trace',
                    '--debug', '--schema', '${}'.format(self.schema),
                    '${}'.format(self.configfile)], ]
        return scripts

    def get_sharedconfig_validation(self):
        script_dir = os.listdir(VALIDATION_SCRIPTS_FOLDER)
        # We can only execute scripts that have execute permissions.
        scripts = [os.path.join(VALIDATION_SCRIPTS_FOLDER, s)
                   for s in script_dir
                   if os.access(os.path.join(
                       VALIDATION_SCRIPTS_FOLDER, s), os.X_OK)]
        return scripts

    def __init__(self, configpath):
        self.configfile = configpath
        if self.filetype == 'json':
            self.scripts = self.get_json_validation()
        elif self.filetype == 'xml':
            self.scripts = self.get_xml_validation()
        elif self.filetype == 'shared_config':
            self.scripts = self.get_sharedconfig_validation()
        else:
            pass


