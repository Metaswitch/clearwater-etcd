"""This file contains the Base class for all of the config types"""
import subprocess
import os

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

    def script_finder_json(self):
        scripts = [['python', self.call_general, self.schema,
                    self.configfile], ]
        return scripts

    def script_finder_xml(self):
        scripts = [['xmllint', '--format', '--pretty', '1', '--load-trace',
                    '--debug', '--schema', '${}'.format(self.schema),
                    '${}'.format(self.configfile)], ]

    def __str__(self):
        return self.name

    def __init__(self, configpath):
        self.configfile = configpath



