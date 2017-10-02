#!/usr/share/clearwater/clearwater-config-manager/env/bin/python
# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.
import subprocess
import etcd
import etcd.client
import os
import argparse
import logging
import difflib
import syslog
import sys

# Constants
DOWNLOADED_CONFIG_PATH = " ~/clearwater-config-manager/staging"
MAXIMUM_CONFIG_SIZE = 100000
VALIDATION_SCRIPTS_FOLDER = "/usr/share/clearwater/clearwater-config-manager/scripts/config_validation/"
LOG_PATH = "/var/log/clearwater-config-manager/allow/cw-config.log"

# Error messages
MODIFIED_WHILE_EDITING = """Another user has modified the configuration since
cw-download_shared_config was last run. Please download the latest version of
shared config, re-apply the changes and try again."""

# Set up logging
logging.basicConfig(filename=LOG_PATH, level=logging.DEBUG)
log = logging.getLogger(__name__)


# Exceptions
class ConfigAlreadyDownloaded(Exception):
    pass


class ConfigDownloadFailed(Exception):
    pass


class ConfigUploadFailed(Exception):
    pass


class ConfigValidationFailed(Exception):
    pass


class NoConfigChanges(Exception):
    pass


class EtcdConnectionFailed(Exception):
    pass


class EtcdMasterConfigChanged(Exception):
    pass


class UserAbort(Exception):
    pass


class ConfigLoader(object):
    """Wrapper around etcd.Client to include information about where to find
    config files in the database."""
    def __init__(self, etcd_client, etcd_key, site):
        # In addition to standard init, we store off the URL to query on the
        # etcd API that will get us our config.
        self._etcd_client = etcd_client
        self.prefix = "/".join(["", etcd_key, site, "configuration"])
        self.download_dir = get_user_download_dir()

    def download_config(self, config_type):
        """Save a copy of a given config type to the download directory.
        Raises a ConfigDownloadFailed exception if unsuccessful."""
        download = self.get_config_and_index(config_type)
        # Write the config to file.
        try:
            with open(os.path.join(self.download_dir,
                                   config_type), 'w') as config_file:
                config_file.write(str(download.value))
        except IOError:
            raise ConfigDownloadFailed(
                "Couldn't save {} to file".format(config_type))

        # We want to keep track of the index the config had in the etcd cluster
        # so we know if it is up to date.
        try:
            with open(os.path.join(self.download_dir,
                                   config_type + ".index"), 'w') as index_file:
                index_file.write(str(download.modifiedIndex))
        except IOError:
            raise ConfigDownloadFailed(
                "Couldn't save {} to file".format(config_type))

    def get_config_and_index(self, config_type):
        try:
            # First we pull the data down from the etcd cluster. This will
            # throw an etcd.EtcdKeyNotFound exception if the config type
            # does not exist in the database.
            download = self._etcd_client.read("/".join([self.prefix, config_type]))
        except etcd.EtcdKeyNotFound:
            raise ConfigDownloadFailed(
                "Failed to download {}".format(config_type))

        return download

    def upload_config(self, config_type, cas_revision):
        """Upload config contained in the specified file to the etcd database.
        Raises a ConfigUploadFailed exception if unsuccessful.
        """
        try:
            with open(os.path.join(self.download_dir,
                                   config_type), 'r') as config_file:
                upload = config_file.read(MAXIMUM_CONFIG_SIZE)
        except IOError:
            raise ConfigUploadFailed(
                "Failed to retrieve {} from file".format(config_type))

        try:
            self._etcd_client.write("/".join([self.prefix, config_type]),
                                    upload,
                                    prevIndex=cas_revision)
        except etcd.EtcdConnectionFailed:
            raise ConfigUploadFailed(
                "Unable to upload {} to etcd cluster".format(config_type))

    # We need this property for the step in upload_config where we log the
    # change in config to file.
    @property
    def full_uri(self):
        """Returns a URI that represents the folder containing the config
        files."""
        return (self._etcd_client.base_uri +
                '/' +
                self._etcd_client.key_endpoint +
                self.prefix)


def main(args):
    """
    Main entry point for script.
    """
    # Regardless of passed arguments we want to delete outdated config to not
    # leave unused files on disk.
    delete_outdated_config_files()

    # Create an etcd client for interacting with the database.
    try:
        log.debug("Getting etcdClient with parameters {}, {}, {}"
                  .format(args.etcd_key, args.site, args.management_ip))
        etcd_client = etcd.client.Client(host=args.management_ip,
                                         port=4000)
        config_loader = ConfigLoader(etcd_client=etcd_client,
                                     etcd_key=args.etcd_key,
                                     site=args.site)
        # TODO we should check the connection to etcd as the bash script did.
    # TODO Handle exceptions properly here
    except Exception:
        sys.exit("Unable to contact the etcd cluster.")

    if args.action == "download":
        log.info("Running in download mode.")
        try:
            download_config(config_loader,
                            args.config_type,
                            args.autoconfirm)
        except ConfigDownloadFailed as e:
            sys.exit(e)
        except UserAbort:
            sys.exit("User aborted.")
        except IOError as e:
            sys.exit(e)

    if args.action == "upload":
        log.info("Running in upload mode.")

        try:
            # TODO - upload and download functions are really
            # massive great big scripts and should hold all the logic
            # for their mode.
            validate_config(args.force)
        except ConfigValidationFailed as exc:
            sys.exit(exc)

        try:
            # TODO - force is different to autoconfirm so we need to pass
            # them separately, right?
            upload_config(config_loader,
                          args.config_type,
                          args.force,
                          args.autoconfirm)
        except UserAbort:
            sys.exit("User aborted.")
        except EtcdMasterConfigChanged:
            # TODO Tell user to redownload and abort
            pass
        except ConfigUploadFailed:
            # TODO Tell user and abort
            pass


def parse_arguments():
    """
    Parse the arguments passed to the script.
    :return:
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--autoconfirm", action="store_true",
                        help="Turns autoconfirm on [default=off]")
    parser.add_argument("--force", action="store_true",
                        help="Turns forcing on [default=off]")
    parser.add_argument("action", type=str, choices=['upload', 'download'],
                        help="The action to perform - upload or download")
    parser.add_argument("config_type", nargs='?', default='shared', type=str,
                        choices=['shared'],
                        help=("The config type to use - shared"
                              " - only one option currently"))
    parser.add_argument("management_ip",
                        help=("The IP address to contact etcd with - this is"
                              "read from the config - do not enter"))
    parser.add_argument("site", help=("always the site you are at, this is"
                                      " read from config - do not enter"))
    parser.add_argument("etcd_key",
                        help=("this is currently always 'clearwater' but may"
                              "be able to be 'CCF' as well in the future - "
                              "this is read from config - do not enter"))

    return parser.parse_args()


def delete_outdated_config_files():
    """
    Deletes all config files in any subfolder of DOWNLOADED_CONFIG_PATH that is
    older than 30 days.
    :return:
    """
    pass


def download_config(config_loader, config_type, autoskip):
    """
    Downloads the config from etcd and saves a copy to
    DOWNLOADED_CONFIG_PATH/<USER_NAME>.
    """
    local_config_path = os.path.join(get_user_download_dir(), config_type)

    if os.path.exists(local_config_path):
        # Ask user to confirm if they want to overwrite the file
        # Continue with download if user confirms
        confirmed = confirm_yn("A local copy of shared_config is already present. "
                               "Continuing will overwrite the file.", autoskip)
        if not confirmed:
            raise UserAbort

    config_loader.download_config(config_type)
    print("Shared configuration downloaded to {}".format(local_config_path))


def validate_config(force=False):
    """
    Validates the config by calling all scripts in the validation folder.
    TODO: also call our validation script
    """
    log.info("Start validating config using user scripts.")
    script_dir = os.listdir(VALIDATION_SCRIPTS_FOLDER)

    # We can only execute scripts that have execute permissions.
    scripts = [os.path.join(VALIDATION_SCRIPTS_FOLDER, s)
               for s in script_dir
               if os.access(os.path.join(VALIDATION_SCRIPTS_FOLDER, s),
                            os.X_OK)]
    for script in scripts:
        try:
            subprocess.check_call(script)
        except subprocess.CalledProcessError:
            if force:
                # In force mode, we override issues with the validation.
                continue
            else:
                raise ConfigValidationFailed(
                    "Validation failed while executing script {}".format(
                        os.path.basename(script)))

    # TODO: add our validation script that should always be run


def upload_config(config_loader, config_type, force=False, autoconfirm=False):
    """
    Uploads the config from DOWNLOADED_CONFIG_PATH/<USER_NAME> to etcd.
    """
    # THERE MAY BE SOMETHING MISSING HERE! In the bash script
    # `upload_shared_config`, we check that the port we expect etcd to be
    # listening on is actually open before doing anything else. It's possible
    # that we don't actually need to do that in this case, because we'll
    # always be doing some sort of initial verification that the connection
    # can be made. But need to confirm that is in fact the case.

    # Check that the file exists.
    config_path = os.path.join(config_loader.download_dir, config_type)
    if not os.path.exists(config_path):
        raise IOError("No shared config found, unable to upload")

    # Compare local and etcd revision number
    # TODO: Error handling for corrupt storage.
    with open(config_path, "r") as f:
        local_config = f.read()
    with open(os.path.join(config_path, ".index"), "r") as f:
        local_revision = int(f.read())
    remote_config_and_index = config_loader.get_config_and_index(config_type)
    remote_revision = remote_config_and_index.modifiedIndex
    remote_config = remote_config_and_index.value

    if local_revision != remote_revision:
        raise EtcdMasterConfigChanged("The remote config changed while editing"
                                      "the config locally. Please redownload"
                                      "the config and reapply your changes.")

    # Provide a diff of the changes and log to syslog
    if not print_diff_and_syslog(local_config, remote_config):
        raise NoConfigChanges

    if not autoconfirm:
        confirmed = confirm_yn("Please check the config changes and confirm that "
                               "you wish to continue with the config upload.")
        if not confirmed:
            raise UserAbort

    # Upload the configuration to the etcd cluster.
    config_loader.upload_config(config_type,
                                remote_revision)

    # Add the node to the restart queue(s)
    # TODO - why are we doing this?
    apply_config_key = subprocess.check_output(
        "/usr/share/clearwater/clearwater-queue-manager/scripts/get_apply_config_key")
    subprocess.call(["/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue",
                     "add",
                     apply_config_key])

    # We need to modify the queue if we're forcing.
    # TODO - what does this do? Do we need to do it?
    subprocess.call(["/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue",
                     "force_true" if force else "force_false",
                     apply_config_key])

    # Delete local config file if upload was successful
    os.remove(config_path)


def confirm_yn(prompt, autoskip=False):
    """Asks the user to confirm they want to make the changes described by the
    prompt passed in. This keeps asking the user until a valid response is
    given. True or false is returned for a yes no input respectively"""

    if autoskip is True:
        log.info('skipping confirmation enabled')
        return True

    question = "Do you want to continue?  [yes/no] "

    while True:
        print('\n{0} '.format(prompt))
        supplied_input = raw_input(question)
        if supplied_input.strip().lower() not in ['y', 'yes', 'n', 'no']:
                print('\n Answer must be yes or no')
        else:
            return supplied_input.strip().lower().startswith('y')


def get_user_name():
    """
    Returns the local user name if no RADIUS server was used and returns the
    user name that was used to authenticate with a RADIUS server, if used.
    """
    # Worth noting that `whoami` behaves differently to `who am i`, we need the
    # latter.
    process = subprocess.Popen(["who", "am", "i"], stdout=subprocess.PIPE)
    output, error = process.communicate()
    return output.split()[0]


def get_user_download_dir():
    """Returns the user-specific directory for downloaded config."""
    return os.path.join(DOWNLOADED_CONFIG_PATH, get_user_name())


def print_diff_and_syslog(config_1, config_2):
    """
    Print a readable diff of changes between two texts and log to syslog.
    """
    config_lines_1 = config_1.splitlines()
    config_lines_2 = config_2.splitlines()

    # We're looking to log meaningful configuration changes, so sort the lines
    # to ignore changes in line ordering.
    config_lines_1.sort()
    config_lines_2.sort()
    difflines = list(difflib.ndiff(config_lines_1, config_lines_2))

    # Pull out nonempty diff lines prefixed by "- "
    deletions = [line[2:] for line in difflines if line.startswith("- ") and len(line) > 2]
    # "Concatenate", "like", "this"
    deletions_str = ", ".join(['"' + line + '"' for line in deletions])

    additions = [line[2:] for line in difflines if line.startswith("+ ") and len(line) > 2]
    additions_str = ", ".join(['"' + line + '"' for line in additions])

    if additions or deletions:
        logstr = "Configuration file change: shared_config was modified by " \
                 "user {}. ".format(get_user_name())
        if deletions:
            logstr += "Lines removed: "
            logstr += deletions_str + ". "
        if additions:
            logstr += "Lines added: "
            logstr += additions_str + "."

        # Force encoding so logstr prints and syslogs nicely
        logstr = logstr.encode("utf-8")

        # Print changes to console so the user can do a sanity check
        print(logstr)

        # Log the changes
        syslog.openlog("audit-log", syslog.LOG_PID)
        syslog.syslog(syslog.LOG_NOTICE, logstr)
        syslog.closelog()

        return True
    else:
        print("No changes detected in shared configuration file.")
        return False


# Call main function if script is executed stand-alone
if __name__ == "__main__":
    arguments = parse_arguments()
    main(arguments)
