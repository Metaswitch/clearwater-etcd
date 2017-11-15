#!/usr/share/clearwater/clearwater-config-manager/env/bin/python
# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.
import subprocess
import etcd
import etcd.client
import os
import pwd
import argparse
import logging
import difflib
import syslog
import sys
import datetime
import time
from metaswitch.clearwater.config_manager.config_type_plugin_loader import load_plugins_in_dir
from metaswitch.common.logging_config import configure_syslog

# Constants
MAXIMUM_CONFIG_SIZE = 1000000
LOG_DIR = "/var/log/clearwater-config-manager"

# The directory on a clearwater node where the subclass config types are stored
PLUGIN_DIR = "/usr/share/clearwater/clearwater-config-access/plugins/"

# The directory under $HOME where config will be downloaded to.
DOWNLOAD_DIR = "clearwater-config-manager"

# Configure logging.
log = logging.getLogger("cw-config.main")

# Error messages that are displayed to the user (error messages on internal
# exceptions are not shown here).
MODIFIED_WHILE_EDITING = ("Another user has modified the configuration since "
"`cw-config download` was last run. Please download the latest version of "
"{}, re-apply the changes and try again.")

NO_CHANGES_TO_CONFIG = ("There are no differences between the local and "
"remote configuration. No upload will be performed.")

CANT_LOAD_LOCAL_CONFIG = ("Unable to load {} from file. Check the local "
"configuration file at {} has not been corrupted.")

CANT_SAVE_LOCAL_CONFIG = ("Unable to save {} to file. Check the user has "
"permissions to write to {}.")

CANT_COMPARE_WITH_MASTER = ("Unable to compare with master configuration "
"file. No upload will be performed.")

UNABLE_TO_UPLOAD = ("Unable to upload {} to the configuration database. The "
"upload has failed.")

NO_CONFIG_FOUND = "There are no ConfigType plugins found at {}".format(
    PLUGIN_DIR)

CLUSTER_NOT_HEALTHY = ("No changes to configuration can be made while the "
"configuration database does not have quorum. Restore connectivity to the "
"uncontactable nodes in the deployment and try again.")

FIRST_DOWNLOAD_WARNING = ("{} is not present in the configuration database. A "
"blank file has been created for you. You can make changes to this and upload "
"as normal.")

FILE_PERMISSIONS_WARNING = ("The file permissions may be incorrect on your "
                            "downloaded files.")


# Exceptions
class ConfigDownloadFailed(Exception):
    """Unable to download config."""
    pass


class ConfigUploadFailed(Exception):
    """Unable to upload config."""
    pass


class ConfigValidationFailed(ConfigUploadFailed):
    """Unable to validate config."""
    pass


class ConfigUnchanged(ConfigUploadFailed):
    """There are no differences between the config to be uploaded and what is
    already on etcd."""


class EtcdConnectionFailed(Exception):
    """Unable to connect to etcd."""
    pass


class EtcdNoQuorum(Exception):
    """Etcd cluster does not have quorum."""
    pass


class UserAbort(Exception):
    """The user has triggered an abort."""
    pass


# These exceptions are raised by the LocalStore class.
class FileTooLarge(IOError):
    """Raised when a config file exceeds MAXIMUM_CONFIG_SIZE."""
    pass


class InvalidRevision(IOError):
    """Raised when the revision file does not contain an integer."""
    pass


class UnableToSaveFile(IOError):
    """Raised if a file cannot be saved to disk."""
    pass


class ConfigLoader(object):
    """Object for interfacing with etcd for uploading and downloading config.
    """
    ETCD_HEALTH_CHECK = ['/usr/bin/clearwater-etcdctl', 'cluster-health']
    ETCD_UNHEALTHY_INDICATORS = ["cluster is unhealthy",
                                 "cluster may be unhealthy"]

    def __init__(self, etcd_client, etcd_key, site):
        # In addition to standard init, we store off the URL to query on the
        # etcd API that will get us our config.
        self._etcd_client = etcd_client
        self.prefix = "/".join(["", etcd_key, site, "configuration"])

        # Make sure that the etcd process is actually contactable.
        self._check_connection()

        # Make sure that the etcd cluster has quorum.
        self._check_etcd_cluster_health()

    def _check_connection(self):
        """Performs a sanity check to make sure that the etcd process is
        actually running."""
        location = ":".join([self._etcd_client.host,
                             str(self._etcd_client.port)])
        try:
            # `nc` is a program that checks whether the specified IP address/
            # port combination is open. When run with the `-z` argument, it
            # does this passively (eg. without actually sending any data).
            subprocess.check_call(["nc",
                                   "-z",
                                   self._etcd_client.host,
                                   str(self._etcd_client.port)])
        except subprocess.CalledProcessError:
            log.error("Unable to connect to etcd database at %s", location)
            raise EtcdConnectionFailed(
                "etcd process not running at {}".format(location))

    def _check_etcd_cluster_health(self):
        """Raises an EtcdNoQuorum exception if the etcd cluster does not have
        quorum."""
        try:
            health_output = subprocess.check_output(self.ETCD_HEALTH_CHECK)
        except subprocess.CalledProcessError:
            # We couldn't even run the health check! something must be wrong.
            raise EtcdNoQuorum()

        if any(ind in health_output for ind in self.ETCD_UNHEALTHY_INDICATORS):
            # The health check has shown there is no quorum!
            raise EtcdNoQuorum()

    def download_config(self, local_store, selected_config):

        """Save a copy of a given config type to the specified local store.
        Raises a ConfigDownloadFailed exception if unsuccessful."""
        value, index = self.get_config_and_index(selected_config)

        # Write the config to file.
        try:
            local_store.save_config_and_revision(selected_config,
                                                 str(index),
                                                 str(value))
        except IOError:
            log.error("Failed to save %s to file", selected_config.name)
            raise ConfigDownloadFailed(
                CANT_SAVE_LOCAL_CONFIG.format(selected_config.name,
                                              local_store.download_dir))

    def get_config_and_index(self, selected_config):
        """Extract the config file and index from etcd."""
        key_path = "/".join([self.prefix, selected_config.name])

        try:
            # First we pull the data down from the etcd cluster. This will
            # throw an etcd.EtcdKeyNotFound exception if the config type
            # does not exist in the database.
            log.debug("Reading etcd config from '%s", key_path)
            download = self._etcd_client.read(key_path)
        except etcd.EtcdKeyNotFound:
            # If the key isn't present, create an empty file with a default
            # revision number. Users can add the first revision!
            log.info("etcd key %s is not present in the database", key_path)
            print FIRST_DOWNLOAD_WARNING.format(selected_config.name)
            first_value = ""
            first_index = 0
            return first_value, first_index

        return download.value, download.modifiedIndex

    def write_config_to_etcd(self,
                             local_store,
                             selected_config,
                             prev_revision,
                             upload):
        """Upload config contained in the specified file to the etcd database.
        Raises a ConfigUploadFailed exception if unsuccessful.
        """
        key_path = "/".join([self.prefix, selected_config.name])

        try:
            if prev_revision == 0:
                log.debug("Writing etcd config to '%s' for the first time")
                self._etcd_client.write(key_path, upload)
            else:
                log.debug("Writing etcd config to '%s'", key_path)
                self._etcd_client.write(key_path,
                                        upload,
                                        prevIndex=prev_revision)

        except etcd.EtcdCompareFailed:
            log.error("Master revision doesn't match local revision")
            raise ConfigUploadFailed(
                MODIFIED_WHILE_EDITING.format(selected_config.name))
        except etcd.EtcdException:
            log.error("Unable to write to etcd database")
            raise ConfigUploadFailed(UNABLE_TO_UPLOAD.format(
                selected_config.file_download_name))


class LocalStore(object):
    """Class for controlling and making changes to the local config."""
    def __init__(self, download_dir = None):
        if download_dir:
            log.debug("Overriding download dir")
            self.download_dir = download_dir
        else:
            log.debug("Using default download dir")
            self.download_dir = get_user_download_dir()

        log.debug("Download dir: %s", self.download_dir)

        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """Make sure that the folder used to store config exists."""
        if not os.path.exists(self.download_dir):
            log.debug("Creating download directory %s", self.download_dir)
            os.makedirs(self.download_dir)
            reset_file_ownership(self.download_dir)

    def _get_config_file_path(self, config_type):
        return os.path.join(self.download_dir, config_type)

    def _get_revision_file_path(self, config_type):
        revision_file_name = "." + config_type + ".index"
        return self._get_config_file_path(revision_file_name)

    # This function is only really used during exception handling. It would be
    # better if we instead passed through the file location as part of the
    # exception (then we could get rid of the duplication here).
    def config_location(self, config_type):
        """Public method for reporting the location of the config file of a
        given type."""
        return self._get_config_file_path(config_type)

    def load_config_and_revision(self, config_type):
        """Returns a tuple containing the config extracted from file and
        the revision number. If there is an issue, it will throw an exception
        of type IOError (or subclass)."""
        log.debug("Loading %s and revision number from file", config_type)
        config_path = self._get_config_file_path(config_type)
        revision_path = self._get_revision_file_path(config_type)
        if not os.path.exists(config_path):
            log.error("%s does not exist", config_path)
            raise IOError("No {} found, unable to upload".format(config_type))
        if not os.path.exists(revision_path):
            log.error("%s does not exist", revision_path)
            raise IOError(
                "No {} revision file found, unable to upload. "
                "Please download {} again.".format(config_type, config_type))
        log.debug("Uploading config from '%s'", config_path)
        log.debug("Using local revision number from '%s'", revision_path)

        # Extract the information from the relevant files.
        local_config = read_from_file(config_path)

        # The revision must be an integer.
        try:
            raw_revision = read_from_file(revision_path)
            local_revision = int(raw_revision)
        except ValueError:
            # The data in the revision file is not an integer!
            log.error("Revision file doesn't contain an integer. Value:\n"
                      "%s", raw_revision)
            raise InvalidRevision

        return local_config, local_revision

    def save_config_and_revision(self, selected_config, index, value):
        """Write the config and revision number to file."""
        config_file_path = self._get_config_file_path(
            selected_config.file_download_name)
        index_file_path = self._get_revision_file_path(
            selected_config.file_download_name)
        log.debug("Writing %s to '%s'.", selected_config.file_download_name,
                  config_file_path)

        try:
            with open(config_file_path, 'w') as config_file:
                config_file.write(value)
            reset_file_ownership(config_file_path)
        except IOError:
            log.error("Failed to write %s to %s",
                      selected_config.file_download_name,
                      config_file_path)
            raise UnableToSaveFile("Unable to save config file on disk.")
        # We want to keep track of the index the config had in the etcd cluster
        # so we know if it is up to date.
        log.debug("Writing revision number to '%s'.", index_file_path)
        try:
            with open(index_file_path, 'w') as index_file:
                index_file.write(index)
            reset_file_ownership(index_file_path)
        except IOError:
            log.error("Failed to write revision number to %s", index_file_path)
            raise UnableToSaveFile("Unable to save revision file on disk.")

    def config_cleanup(self, config_type):
        """This function cleans up the config from the local store after a
        successful upload to avoid confusion"""
        log.debug("Cleaning up old config")
        config_path = self._get_config_file_path(config_type)
        revision_path = self._get_revision_file_path(config_type)
        os.remove(config_path)
        os.remove(revision_path)


def main(args, config_filename):
    """
    Main entry point for script.
    """
    # Set up logging to syslog.
    configure_syslog("clearwater-config-manager", args.log_level)

    # Regardless of passed arguments we want to delete outdated config to not
    # leave unused files on disk.
    delete_outdated_config_files()

    # Create an etcd client for interacting with the database.
    try:
        log.debug("Getting etcdClient with parameters %s, 4000",
                  args.management_ip)
        etcd_client = etcd.client.Client(host=args.management_ip,
                                         port=4000)
        local_store = LocalStore(args.download_dir)

        config_location = local_store.config_location(config_filename)

        selected_config = lookup_config_type(args.config_type, config_location)
        config_loader = ConfigLoader(etcd_client=etcd_client,
                                     etcd_key=args.etcd_key,
                                     site=args.site)
    except (etcd.EtcdException, EtcdConnectionFailed):
        log.error("etcd cluster uncontactable")
        sys.exit("Unable to contact the etcd cluster.")
    except EtcdNoQuorum:
        log.error("etcd cluster doesn't have quorum")
        sys.exit(CLUSTER_NOT_HEALTHY)

    if args.action == "download":
        log.info("User %s triggered download of %s",
                 get_user_name(),
                 args.config_type)
        try:
            download_config(config_loader,
                            local_store,
                            selected_config,
                            args.autoconfirm)
        except (UserAbort, ConfigDownloadFailed) as exc:
            log.error("Download failed")
            sys.exit(exc)

    if args.action == "upload":
        log.info("User %s triggered upload of %s",
                 get_user_name(),
                 args.config_type)
        try:
            upload_verified_config(config_loader,
                                   local_store,
                                   selected_config,
                                   args.force,
                                   args.autoconfirm)
        except ConfigUnchanged:
            # If there are no changes to the config, we don't execute an
            # upload. But that doesn't mean there was a failure - the config
            # on etcd is what the user wanted it to be. We print a message to
            # the user and return a zero error code.
            print NO_CHANGES_TO_CONFIG
        except (UserAbort, ConfigUploadFailed) as exc:
            log.error("Upload failed")
            sys.exit(exc)


def lookup_config_type(config_type, config_location):
    """
    This takes the string defining the config_type and a string of the
    config_location which is where the config is downloaded to and returns
    an instance of the class containing data on the config type selected
    """
    config_classes = load_plugins_in_dir(PLUGIN_DIR, config_location)

    # There is no need for an else part as the parse_arguments function
    # will gurantee there is always a match
    return next(config for config in config_classes
                if config.name == config_type)


def parse_arguments():
    """
    Parse the arguments passed to the script.
    The options for config type are designated by the plugins available
    :return:
    """
    # Pick the options to appear in argument parsing. the config types are
    # loaded as plugin classes onto the node so only the config files available
    # on the node are able to be changed on the node.
    config_classes = load_plugins_in_dir(PLUGIN_DIR)

    if not config_classes:
        # we need to raise an error as otherwise you will always get refused by
        # the arg parsing. Due to the fact there will be a compulsory selection
        # with no choices available.
        log.error(NO_CONFIG_FOUND)
        sys.exit(NO_CONFIG_FOUND)

    config_choice_help = '\n'.join(choice.help_info for choice in config_classes)
    config_choices = [choice.name for choice in config_classes]

    def config_error(config):
        """This verifies the config_type choice and prints a custom
           error message if the choice is wrong"""
        choices = config_choices
        if config not in choices:
            msg = ("invalid choice: {} (choose from {}).\nHowever some "
                   "configuration is only available on a specific node type.\n"
                   "Check that you are using the correct node type for the \n"
                   "configuration type you are trying to modify.".format(
                       config, ', '.join(choices)))
            raise argparse.ArgumentTypeError(msg)
        return config

    parser = argparse.ArgumentParser(prog='cw-config',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--autoconfirm", action="store_true",
                        help="Turns autoconfirm on [default=off]")
    parser.add_argument("--force", action="store_true",
                        help="Turns forcing on [default=off]")

    # Hidden option to allow you to specify which directory you want to
    # download files to/upload files from.
    parser.add_argument("--dir", dest='download_dir',
                        help=argparse.SUPPRESS)

    # Logging options
    parser.add_argument("--log-level",
                        type=int,
                        default=logging.INFO,
                        help="""Set to {} for DEBUG,
    Set to {} for INFO,
    Set to {} for WARNING,
    Set to {} for ERROR,
    Set to {} for CRITICAL.
    All logs of this level or above will be
    written to file.
    DEFAULT is INFO""".format(logging.DEBUG,
                              logging.INFO,
                              logging.WARNING,
                              logging.ERROR,
                              logging.CRITICAL))

    # Positional arguments
    parser.add_argument("action",
                        type=str,
                        choices=['upload', 'download'],
                        help="The action to perform - {upload | download}",
                        metavar='action')
    parser.add_argument("config_type",
                        type=config_error,
                        help=config_choice_help,
                        metavar='config_type')
    parser.add_argument("--management_ip", required=True,
                        help=argparse.SUPPRESS)
    parser.add_argument("--site", required=True, help=argparse.SUPPRESS)
    parser.add_argument("--etcd_key", required=True, help=argparse.SUPPRESS)

    args = parser.parse_args()
    config_filename = next(config.file_download_name for config in config_classes
                           if config.name == args.config_type)

    return args, config_filename


def delete_outdated_config_files():
    """
    Deletes all config files in any subfolder of DOWNLOADED_CONFIG_PATH that is
    older than 30 days. Note that this is the download destination. No attempt
    is made to police files downloaded to non-standard directories.
    :return:
    """
    log.debug("Deleting outdated config files")
    date_now = datetime.date.today()
    delete_date = date_now - datetime.timedelta(days=30)
    config_folder = get_base_download_dir()
    for root, _, files in os.walk(config_folder, topdown=False):
        for name in files:
            filepath = (os.path.join(root, name))
            file_time = time.localtime(os.path.getmtime(filepath))
            file_date = datetime.date(file_time.tm_year, file_time.tm_mon,
                                      file_time.tm_mday)
            if file_date > delete_date:
                pass
            else:
                log.debug("Deleting %s", name)
                os.remove(filepath)


def download_config(config_loader, local_store, selected_config, autoskip=False):
    """
    Downloads the config from etcd and saves a copy to
    DOWNLOADED_CONFIG_PATH/<USER_NAME>.
    """
    local_config_path = local_store.config_location(selected_config.file_download_name)

    if os.path.exists(local_config_path):
        # Ask user to confirm if they want to overwrite the file
        # Continue with download if user confirms
        log.debug("Check user wants to overwrite existing file")
        confirmed = confirm_yn(
            "A local copy of {} is already present. "
            "Continuing will overwrite the file.".format(selected_config.file_download_name),
            autoskip)
        if not confirmed:
            log.info("User aborted download")
            raise UserAbort

    config_loader.download_config(local_store, selected_config)
    print("{} downloaded to {}".format(selected_config.name,
                                       local_config_path))


def upload_verified_config(config_loader,
                           local_store,
                           selected_config,
                           force=False,
                           autoconfirm=False):
    """Verifies the config, then uploads it to etcd."""

    # check the file has been downloaded, otherwise raise specific error
    config_location = local_store.config_location(selected_config.file_download_name)
    if not os.path.exists(config_location):
        log.error("The config file does not exist at %s", config_location)
        raise ConfigUploadFailed(
            "The config file to upload does not exist at {}".format(
                config_location))

    validate_config(selected_config, force)

    # An exception should have been thrown if validation fails, so we should
    # only reach this point if the config has been validated successfully.
    upload_config(autoconfirm, config_loader, selected_config,
                  force, local_store)


def validate_config(selected_config, force=False):
    """
    Validates the config by calling all scripts in the validation folder.
    """

    # selected_config is an instance of the ConfigType class. validate() uses
    # different scripts to validate against for different ConfigType classes.
    failed_scripts, error_lines = selected_config.validate()

    # In the forcing case, we proceed even if there have been failures, but
    # otherwise we want to bail out at this point.
    if not force and failed_scripts:
        log.error("One or more validation scripts have failed, aborting")
        raise ConfigValidationFailed(
            "Validation failed while executing scripts:\n"
            " {}\n"
            "Errors:\n"
            " {}".format("\n ".join(os.path.basename(script)
                                    for script in failed_scripts),
                         "\n ".join(error_lines)))

    if failed_scripts:
        # We can only get here in the forcing case.
        print "Continuing despite failed validation"
    else:
        print "Config successfully validated"


def upload_config(autoconfirm, config_loader, selected_config, force, local_store):
    """Read the relevant config from file and upload it to etcd."""
    remote_revision, upload_string = ready_for_upload_checks(autoconfirm,
                                                             config_loader,
                                                             selected_config,
                                                             local_store)

    # Upload the configuration to the etcd cluster. This will trigger the
    # queue manager to schedule nodes to be restarted.
    config_loader.write_config_to_etcd(local_store,
                                       selected_config,
                                       remote_revision,
                                       upload_string)

    # Clearwater can be run with multiple etcd clusters. The apply_config_key
    # variable stores the information about which etcd cluster the changes
    # should be applied to.
    apply_config_key = subprocess.check_output(
        "/usr/share/clearwater/clearwater-queue-manager/scripts/get_apply_config_key")

    # If the config changes are being forced through, the queue manager needs
    # to be made aware so it knows to push on in the case of an error when
    # applying the config to a node.
    subprocess.call(["/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue",
                     "force_true" if force else "force_false",
                     apply_config_key])

    # If we reach this point then config upload was successful. Cleaning up
    # the config file we've uploaded makes sure we don't cause confusion later.
    local_store.config_cleanup(selected_config.file_download_name)

    print "{} successfully uploaded".format(selected_config.name)


def ready_for_upload_checks(autoconfirm,
                            config_loader,
                            selected_config,
                            local_store):
    """Make sure that we can and should upload config. Returns the current
    revision of the master config upload if we should proceed, otherwise throws
    a ConfigUploadFailed exception."""
    try:
        local_config, local_revision = local_store.load_config_and_revision(
            selected_config.file_download_name)
    except IOError:
        log.error("Can't read %s from %s",
                  selected_config.file_download_name,
                  local_store.config_location(selected_config.file_download_name))
        raise ConfigUploadFailed(
            CANT_LOAD_LOCAL_CONFIG.format(
                selected_config.file_download_name,
                local_store.config_location(selected_config.file_download_name)))

    # In order to confirm that no changes have been made while the user has
    # been editing locally, we download a copy of the master config to compare
    # against.
    try:
        remote_config, remote_revision = config_loader.get_config_and_index(
            selected_config)
    except ConfigDownloadFailed:
        log.error("Unable to download %s from config database to compare it "
                  "with local config", selected_config.name)
        raise ConfigUploadFailed(CANT_COMPARE_WITH_MASTER)

    # Users are not allowed to upload changes if someone else has uploaded
    # config to the etcd cluster in the meantime.
    if local_revision != remote_revision:
        log.error("Master has different revision to local %s", selected_config.file_download_name)
        raise ConfigUploadFailed(MODIFIED_WHILE_EDITING.format(selected_config.file_download_name))

    # Provide a diff of the changes and log to syslog
    if not print_diff_and_syslog(selected_config.name, remote_config, local_config):
        # We don't bother uploading if there are no changes to upload.
        log.error("No differences between local and master %s", selected_config.name)
        raise ConfigUnchanged

    if not autoconfirm:
        confirmed = confirm_yn(
            "Please check the config changes and confirm that "
            "you wish to continue with the config upload.")
        if not confirmed:
            log.info("User cancelled config upload")
            raise UserAbort

    log.debug("All checks passed, ready for config upload")
    return remote_revision, local_config


def confirm_yn(prompt, autoskip=False):
    """Asks the user to confirm they want to make the changes described by the
    prompt passed in. This keeps asking the user until a valid response is
    given. True or false is returned for a yes no input respectively"""

    if autoskip:
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
    Note that this only works if called from the terminal.
    """
    # Worth noting that `whoami` behaves differently to `who am i`, we need the
    # latter.
    process = subprocess.check_output(["who", "am", "i"])
    splits = process.split()
    if splits:
        # The format of `who am i` looks like this:
        #
        # clearwater      pts/1        2017-10-30 18:25 (:0)
        #
        # This is the login that is associated with the current user.
        return splits[0]
    else:
        # `who am i` has not returned anything! This happens if the connection
        # has been made via the console rather than over ssh. In these
        # situations, we can use the $USER environment variable as a backup.
        return os.getenv("USER")


def get_user_download_dir():
    """Returns the user-specific directory for downloaded config."""
    username = get_user_name()
    sub_dir = username if username is not None else ""
    return os.path.join(get_base_download_dir(), sub_dir)


def get_base_download_dir():
    """Returns the base directory for downloaded config."""
    base_dir = os.getenv("HOME") or os.getcwd()
    if base_dir is None:
        log.error("There must be a directory to download config to")
        raise RuntimeError("No directory found.")
    return os.path.join(base_dir, DOWNLOAD_DIR)


def print_diff_and_syslog(config_type, config_1, config_2):
    """
    Print a readable diff of changes between two texts and log to syslog.
    Returns True if there are changes, that need to be uploaded, or False if
    the two are the same.
    """
    # We do care about line order changes (so don't sort lines) as we want line
    # changes to count as config changes for allowing the config to upload.
    config_lines_1 = config_1.splitlines()
    config_lines_2 = config_2.splitlines()

    # Get a list of diffs, like the lines of the output you'd see when you
    # run `diff` on the command line:
    # * removed lines are prefixed with "- ".
    # * added lines are prefixed with "+ ".
    difflines = list(difflib.ndiff(config_lines_1,
                                   config_lines_2))

    # We don't want to print out the '+' or '-': we have our own way of
    # describing diffs.
    deletions = [line[2:] for line in difflines
                 if line.startswith("- ") and len(line) > 2]
    additions = [line[2:] for line in difflines
                 if line.startswith("+ ") and len(line) > 2]

    # If something is in both deletions and additions it means the line has
    # moved so will be in third category and removed from the other two.
    moved = [x for x in deletions for y in additions if x == y]
    for item in moved:
        deletions.remove(item)
        additions.remove(item)

    if additions or deletions or moved:
        header = "Configuration file change: user {} has modified {}.".format(
            get_user_name(),
            config_type)

        # For the syslog, we want the diff output on one line.
        # For the UI, we want to output on multiple lines, as it's
        # much clearer.
        syslog_str = header
        output_str = header
        if deletions:
            syslog_str += "Lines removed: "
            output_str += "\n Lines removed:\n"
            syslog_str += ", ".join(['"' + line + '"' for line in deletions])
            output_str += "\n".join(['"' + line + '"' for line in deletions])
        if additions:
            syslog_str += "Lines added: "
            output_str += "\n Lines added:\n"
            syslog_str += ", ".join(['"' + line + '"' for line in additions])
            output_str += "\n".join(['"' + line + '"' for line in additions])
        if moved:
            syslog_str += "Lines moved: "
            output_str += "\n Lines moved:\n"
            syslog_str += ", ".join(['"' + line + '"' for line in moved])
            output_str += "\n".join(['"' + line + '"' for line in moved])

        # Force encoding so logstr prints and syslogs nicely
        syslog_str = syslog_str.encode("utf-8")

        # Print changes to console so the user can do a sanity check
        log.info(output_str)
        print(output_str)

        # Log the changes
        syslog.openlog("audit-log", syslog.LOG_PID)
        syslog.syslog(syslog.LOG_NOTICE, syslog_str, facility=syslog.LOG_AUTH)
        syslog.closelog()

        return True
    else:
        print("No changes detected in {} file.").format(config_type)
        return False


def read_from_file(file_path):
    """Run some basic checks against a file to check it hasn't been
    corrupted. If it hasn't, return a string containing its contents.
    Otherwise, throw an exception that subclasses IOError."""
    try:
        with open(file_path, "r") as open_file:
            contents = open_file.read(MAXIMUM_CONFIG_SIZE)

            if open_file.read(1) != '':
                # The file is so big that it cannot be read in one go. It's
                # probably corrupted.
                log.error(
                    "%s file exceeds %s bytes. It is probably corrupted.",
                    file_path,
                    MAXIMUM_CONFIG_SIZE)
                raise FileTooLarge
    except IOError:
        log.error("Unable to read from %s", file_path)
        raise

    return contents

def reset_file_ownership(filepath):
    """If a user runs this module with `sudo`, any created files or directories
    will be owned by root. This may prevent users from making subsequent
    modifications to them. This function resets the permissions on the
    specified file to that of the user who ran the command, rather than root.
    """
    if os.getenv('SUDO_USER'):
        # The script is only being run as sudo if the `SUDO_USER` environment
        # variable is set.
        try:
            pwnam = pwd.getpwnam(os.getenv('SUDO_USER'))
            os.chown(filepath, pwnam.pw_uid, pwnam.pw_gid)
        except OSError:
            # Oh well, we tried.
            print FILE_PERMISSIONS_WARNING


# Call main function if script is executed stand-alone
if __name__ == "__main__":  # pragma: no cover
    arguments, filename = parse_arguments()  # pragma: no cover
    main(arguments, filename)  # pragma: no cover
