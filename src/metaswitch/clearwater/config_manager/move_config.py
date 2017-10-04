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
import datetime
import time

# Constants
MAXIMUM_CONFIG_SIZE = 1000000
VALIDATION_SCRIPTS_FOLDER = "/usr/share/clearwater/clearwater-config-manager/scripts/config_validation/"
LOG_PATH = "/var/log/clearwater-config-manager/allow/cw-config.log"

# Error messages
MODIFIED_WHILE_EDITING = """Another user has modified the configuration since
cw-download_shared_config was last run. Please download the latest version of
shared config, re-apply the changes and try again."""

# Set up logging
# TODO: Make sure that logging wraps properly - use python common's logging infra?
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

        # Make sure that the etcd process is actually contactable.
        self._check_connection()

    def _check_connection(self):
        """Performs a sanity check to make sure that the etcd process is
        actually running."""
        location = ":".join([self._etcd_client.host, self._etcd_client.port])
        try:
            subprocess.check_call(["nc", "-z", location])
        except CalledProcessError:
            raise EtcdConnectionFailed(
                "etcd process not running at {}".format(location))

    def _ensure_config_dir(self):
        """Make sure that the folder used to store config exists."""
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    def download_config(self, config_type):
        """Save a copy of a given config type to the download directory.
        Raises a ConfigDownloadFailed exception if unsuccessful."""
        self._ensure_config_dir()
        config_file_path = os.path.join(self.download_dir, config_type)
        index_file_path = config_file_path + ".index"
        download = self.get_config_and_index(config_type)

        # Write the config to file.
        try:
            log.debug("Writing config to '%s'.", config_file_path)
            with open(config_file_path, 'w') as config_file:
                config_file.write(str(download.value))
        except IOError:
            raise ConfigDownloadFailed(
                "Couldn't save {} to file".format(config_type))

        # We want to keep track of the index the config had in the etcd cluster
        # so we know if it is up to date.
        try:
            log.debug("Writing config to '%s'.", index_file_path)
            with open(index_file_path, 'w') as index_file:
                index_file.write(str(download.modifiedIndex))
        except IOError:
            raise ConfigDownloadFailed(
                "Couldn't save {} to file".format(config_type))

    def get_config_and_index(self, config_type):
        key_path = "/".join([self.prefix, config_type])

        try:
            # First we pull the data down from the etcd cluster. This will
            # throw an etcd.EtcdKeyNotFound exception if the config type
            # does not exist in the database.
            log.debug("Reading etcd config from '%s", key_path)
            download = self._etcd_client.read(key_path)
        except etcd.EtcdKeyNotFound:
            raise ConfigDownloadFailed(
                "Failed to download {}".format(config_type))

        return download

    def upload_config(self, config_type, cas_revision):
        """Upload config contained in the specified file to the etcd database.
        Raises a ConfigUploadFailed exception if unsuccessful.
        """
        config_file_path = os.path.join(self.download_dir, config_type)
        key_path = "/".join([self.prefix, config_type])

        try:
            log.debug("Reading local config from '%s'", config_file_path)
            with open(config_file_path, 'r') as config_file:
                upload = config_file.read(MAXIMUM_CONFIG_SIZE)

                # The MAXIMUM_CONFIG_SIZE should have been big enough to store
                # all of the config in the file. If there is still config to
                # read from the file, the config file is too big and is
                # probably corrupted.
                if config_file.read(1) != '':
                    raise ConfigUploadFailed(
                        "Config exceeds {} bytes. It is too big "
                        "to upload.".format(MAXIMUM_CONFIG_SIZE))
        except IOError:
            # This exception will be thrown in the following cases:
            # - The download directory doesn't exist
            # - The config file doesn't exist in the download directory
            # - The config file is not readable
            raise ConfigUploadFailed(
                "Failed to retrieve {} from file".format(config_type))

        try:
            log.debug("Writing etcd config to '%s'", key_path)
            self._etcd_client.write(key_path,
                                    upload,
                                    prevIndex=cas_revision)
        except etcd.EtcdConnectionFailed:
            raise ConfigUploadFailed(
                "Unable to upload {} to etcd cluster".format(config_type))
        except etcd.EtcdCompareFailed:
            raise ConfigUploadFailed(
                "Unable to upload {} to etcd cluster as the version changed "
                "while editing locally.".format(config_type))

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
        log.debug("Getting etcdClient with parameters %s, %s, %s",
                  args.etcd_key,
                  args.site,
                  args.management_ip)
        etcd_client = etcd.client.Client(host=args.management_ip,
                                         port=4000)
        config_loader = ConfigLoader(etcd_client=etcd_client,
                                     etcd_key=args.etcd_key,
                                     site=args.site)
    except (etcd.EtcdException, EtcdConnectionFailed):
        sys.exit("Unable to contact the etcd cluster.")

    if args.action == "download":
        log.info("Running in download mode.")
        try:
            download_config(config_loader,
                            args.config_type,
                            args.autoconfirm)
        except (ConfigDownloadFailed, IOError) as exc:
            sys.exit(exc)
        except UserAbort:
            sys.exit("User aborted.")

    if args.action == "upload":
        log.info("Running in upload mode.")
        try:
            upload_config(config_loader,
                          args.config_type,
                          args.force,
                          args.autoconfirm)
        except UserAbort:
            sys.exit("User aborted.")
        except EtcdMasterConfigChanged:
            sys.exit("The config changed on etcd master while editing locally."
                     "Please redownload the config and apply your changes.")
        except ConfigUploadFailed:
            sys.exit("The config upload failed. Please try again.")
        except (ConfigValidationFailed, IOError) as exc:
            sys.exit(exc)


def parse_arguments():
    """
    Parse the arguments passed to the script.
    :return:
    """
    parser = argparse.ArgumentParser(prog='cw-config', description=("You must "
                                     "pick an action either upload or download"
                                     " and then also a config_type currently"
                                     " only shared_config"))
    parser.add_argument("--autoconfirm", action="store_true",
                        help="Turns autoconfirm on [default=off]")
    parser.add_argument("--force", action="store_true",
                        help="Turns forcing on [default=off]")
    parser.add_argument("action", type=str, choices=['upload', 'download'],
                        help="The action to perform - upload or download",
                        metavar='action')
    parser.add_argument("config_type", type=str, choices=['shared_config'],
                        help=("The config type to use - shared_config - only "
                        "one option currently"), metavar='config_type')
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

    date_now = datetime.date.today()
    delete_date = date_now - datetime.timedelta(days=30)
    shared_config_folder = get_base_download_dir()
    for root, dirs, files in os.walk(shared_config_folder, topdown=False):
        for name in files:
            filepath = (os.path.join(root, name))
            file_time = time.localtime(os.path.getmtime(filepath))
            file_date = datetime.date(file_time.tm_year, file_time.tm_mon,
                                      file_time.tm_mday)
            if file_date > delete_date:
                pass
            else:
                os.remove(filepath)


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
    """
    log.info("Start validating config using user scripts.")
    script_dir = os.listdir(VALIDATION_SCRIPTS_FOLDER)

    # We can only execute scripts that have execute permissions.
    scripts = [os.path.join(VALIDATION_SCRIPTS_FOLDER, s)
               for s in script_dir
               if os.access(os.path.join(VALIDATION_SCRIPTS_FOLDER, s),
                            os.X_OK)]
    # TODO: log a warning if we are skipping validation scripts.
    # TODO: Make sure that useful diags are printed by the
    #       validation scripts.
    # TODO: Run all the scripts to give customers full warning
    #       of all errors.
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

    # TODO: if force is True, check that we are root, otherwise error out

    # Check that the file exists.
    config_path = os.path.join(config_loader.download_dir, config_type)
    revision_path = config_path + ".index"
    log.debug("Uploading config from '%s'", config_path)
    log.debug("Using local revision number from '%s'", revision_path)

    if not os.path.exists(config_path):
        raise IOError("No shared config found, unable to upload")
    if not os.path.exists(revision_path):
        raise IOError("No shared config revision file found, unable to "
                      "upload. Please re-download the shared config again.")

    # Validate the config
    validate_config(force)

    # Compare local and etcd revision number
    # TODO: Error handling for corrupt storage.
    with open(config_path, "r") as f:
        local_config = f.read()
    with open(revision_path, "r") as f:
        local_revision = int(f.read())
    remote_config_and_index = config_loader.get_config_and_index(config_type)
    remote_revision = remote_config_and_index.modifiedIndex
    remote_config = remote_config_and_index.value

    if local_revision != remote_revision:
        raise EtcdMasterConfigChanged("The remote config changed while editing"
                                      "the config locally. Please redownload"
                                      "the config and reapply your changes.")

    # Provide a diff of the changes and log to syslog
    if not print_diff_and_syslog(remote_config, local_config):
        raise NoConfigChanges

    if not autoconfirm:
        confirmed = confirm_yn("Please check the config changes and confirm that "
                               "you wish to continue with the config upload.")
        if not confirmed:
            raise UserAbort

    # Upload the configuration to the etcd cluster.
    config_loader.upload_config(config_type,
                                remote_revision)

    # When changes are made to the config, we tell the queue manager. It
    # coordinates restarting all the nodes in the cluster so that we don't lose
    # service.
    #
    # Clearwater can be run with multiple etcd clusters. The apply_config_key
    # variable stores the information about which etcd cluster the changes
    # should be applied to.
    # TODO: What happens if we try to change the etcd cluster configuration as
    #       part of this script?
    apply_config_key = subprocess.check_output(
        "/usr/share/clearwater/clearwater-queue-manager/scripts/get_apply_config_key")
    # TODO: This is a bash script that calls a python script under the covers.
    #       Ideally we would adjust the modify_nodes_in_queue script so it
    #       could be imported and called directly (it's an uncommented mess
    #       though).
    subprocess.call(["/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue",
                     "add",
                     apply_config_key])

    # If the config changes are being forced through, the queue manager needs
    # to be made aware so it can apply the changes to the other nodes in the
    # cluster properly.
    subprocess.call(["/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue",
                     "force_true" if force else "force_false",
                     apply_config_key])

    # Delete local config file if upload was successful
    os.remove(config_path)


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
    """
    # Worth noting that `whoami` behaves differently to `who am i`, we need the
    # latter.
    process = subprocess.Popen(["who", "am", "i"], stdout=subprocess.PIPE)
    output, error = process.communicate()
    return output.split()[0]


def get_user_download_dir():
    """Returns the user-specific directory for downloaded config."""
    return os.path.join(get_base_download_dir(), get_user_name())


def get_base_download_dir():
    """Returns the base directory for downloaded config."""
    home = os.getenv("HOME")
    if home is None:
        raise RuntimeError("No home directory found.")
    return os.path.join(home, 'clearwater-config-manager/staging')


def print_diff_and_syslog(config_1, config_2):
    """
    Print a readable diff of changes between two texts and log to syslog.
    """
    # We don't care about line ordering changes, so first,
    # clean up the data into sorted lists of lines.
    config_lines_1 = config_1.splitlines()
    config_lines_2 = config_2.splitlines()
    config_lines_1.sort()
    config_lines_2.sort()

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

    if additions or deletions:
        header = ("Configuration file change: shared_config was modified by "
                  "user {}. ").format(get_user_name())

        # For the syslog, we want the diff output on one line.
        # For the UI, we want to output on multiple lines, as it's
        # much clearer.
        syslog_str = header
        output_str = header
        if deletions:
            syslog_str += "Lines removed: "
            output_str += "Lines removed:\n"
            syslog_str += ", ".join(['"' + line + '"' for line in deletions])
            output_str += "\n".join(['"' + line + '"' for line in deletions])
        if additions:
            syslog_str += "Lines added: "
            output_str += "Lines added:\n"
            syslog_str += ", ".join(['"' + line + '"' for line in additions])
            output_str += "\n".join(['"' + line + '"' for line in additions])

        # Force encoding so logstr prints and syslogs nicely
        syslog_str = syslog_str.encode("utf-8")

        # Print changes to console so the user can do a sanity check
        print(output_str)

        # Log the changes
        syslog.openlog("audit-log", syslog.LOG_PID)
        syslog.syslog(syslog.LOG_NOTICE, syslog_str)
        syslog.closelog()

        return True
    else:
        print("No changes detected in shared configuration file.")
        return False


# Call main function if script is executed stand-alone
if __name__ == "__main__":
    arguments = parse_arguments()
    main(arguments)
