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
import log_shared_config
import argparse

# Constants
SHARED_CONFIG_PATH = "/etc/clearwater/shared_config"
DOWNLOADED_CONFIG_PATH = " ~/clearwater-config-manager/staging"
MAXIMUM_CONFIG_SIZE = 100000
VALIDATION_SCRIPTS_FOLDER = "/usr/share/clearwater/clearwater-config-manager/scripts/config_validation/"

# Error messages
MODIFIED_WHILE_EDITING = """Another user has modified the configuration since
cw-download_shared_config was last run. Please download the latest version of
shared config, re-apply the changes and try again."""


# Exceptions
class ConfigAlreadyDownloaded(Exception):
    pass


class ConfigDownloadFailed(Exception):
    pass


class ConfigUploadFailed(Exception):
    pass


class ConfigValidationFailed(Exception):
    pass


class EtcdConnectionFailed(Exception):
    pass


class EtcdMasterConfigChanged(Exception):
    pass


class UserAbort(Exception):
    pass


class etcdClient(etcd.client.Client):
    """Wrapper around etcd.Client to include information about where to find
    config files in the database."""
    def __init__(self, etcd_key, site, *args, **kwargs):
        """In addition to standard init, we store off the URL to query on the
        etcd API that will get us our config."""
        super(etcdClient, self).__init__(self, args, kwargs)
        self.prefix = "/".join(["", etcd_key, site, "configuration"])
        self.download_dir = os.path.join(DOWNLOADED_CONFIG_PATH,
                                         get_user_name())

    def download_config(self, config_type):
        """Save a copy of a given config type to the download directory.
        Raises a ConfigDownloadFailed exception if unsuccessful."""
        try:
            # First we pull the data down from the etcd cluster. This will
            # throw an etcd.EtcdKeyNotFound exception if the config type
            # does not exist in the database.
            download = self.read("/".join([self.prefix, config_type]))
        except etcd.EtcdKeyNotFound:
            raise ConfigDownloadFailed(
                "Failed to download {}".format(config_type))

        # Write the config to file.
        try:
            with open(os.path.join(self.download_dir,
                                   config_type), 'w') as config_file:
                config_file.write(download.value)
        except IOError:
            raise ConfigDownloadFailed(
                "Couldn't save {} to file".format(config_type))

        # We want to keep track of the index the config had in the etcd cluster
        # so we know if it is up to date.
        try:
            with open(os.path.join(self.download_dir,
                                   config_type + ".index"), 'w') as index_file:
                index_file.write(download.modifiedIndex)
        except IOError:
            raise ConfigDownloadFailed(
                "Couldn't save {} to file".format(config_type))

    def upload_config(self, config_type, **kwargs):
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
            self.write("/".join([self.prefix, config_type]), upload, **kwargs)
        except etcd.EtcdConnectionFailed:
            raise ConfigUploadFailed(
                "Unable to upload {} to etcd cluster".format(config_type))

    # We need this property for the step in upload_config where we log the
    # change in config to file.
    @property
    def full_uri(self):
        """Returns a URI that represents the folder containing the config
        files."""
        return "/".join([self.base_uri,
                         self.key_endpoint,
                         self.prefix])


def main(args):
    """
    Main entry point for script.
    """
    # TODO Set up logging

    # Regardless of passed arguments we want to delete outdated config to not
    # leave unused files on disk.
    delete_outdated_config_files()

    # Define an etcd client for interacting with the database.
    try:
        etcd_client = etcdClient(etcd_key=args.etcd_key,
                                 site=args.site,
                                 host=args.management_ip,
                                 port=4000)
        #TODO we should check the connection to etcd.
    except:
        raise EtcdConnectionFailed

    if args.action == "download":
        try:
            download_config(etcd_client, args.config_type)
        except ConfigDownloadFailed:
            # Abort and tell user
            pass

    if args.action == "upload":
        try:
            validate_config(args.force)
            upload_config(etcd_client, args.config_type, args.force)
        except UserAbort:
            # Abort and tell user
            pass
        except EtcdMasterConfigChanged:
            # Tell user to redownload and abort
            pass
        except ConfigUploadFailed:
            # Tell user and abort
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
    parser.add_argument("management_IP",
                        help="The IP address to contact etcd with")

    return parser.parse_args()


def delete_outdated_config_files():
    """
    Deletes all config files in any subfolder of DOWNLOADED_CONFIG_PATH that is
    older than 30 days.
    :return:
    """
    pass


def download_config(client, config_type):
    """
    Downloads the config from etcd and saves a copy to
    DOWNLOADED_CONFIG_PATH/<USER_NAME>.
    """
    if os.path.exists(os.path.join(DOWNLOADED_CONFIG_PATH,
                                       get_user_name(),
                                       config_type)):
        # Ask user to confirm if they want to overwrite the file
        # Continue with download if user confirms

    client.download_config(config_type)


def validate_config(force=False):
    """
    Validates the config by calling all scripts in the validation folder.
    """
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
                # KAF: Changed this to Failed from Error - MD6 to confirm OK.
                raise ConfigUploadFailed(
                    "Validation failed while executing script {}".format(
                        os.path.basename(script)))


def upload_config(client, config_type, force=False):
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
    if not os.path.exists(os.path.join(DOWNLOADED_CONFIG_PATH,
                                       get_user_name(),
                                       config_type)):
        raise IOError("No shared config found, unable to upload")

    # Log the changes.
    log_shared_config.log_config(client.full_uri)

    # Upload the configuration to the etcd cluster.
    client.upload_config(config_type)

    # Add the node to the restart queue(s)
    apply_config_key = subprocess.check_output("/usr/share/clearwater/clearwater-queue-manager/scripts/get_apply_config_key")
    subprocess.call(["/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue",
                     "add",
                     apply_config_key])

    # We need to modify the queue if we're forcing.
    subprocess.call(["/usr/share/clearwater/clearwater-queue-manager/scripts/modify_nodes_in_queue",
                     "force_true" if force else "force_false",
                     apply_config_key])


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


# Call main function if script is executed stand-alone
if __name__ == "__main__":
    arguments = parse_arguments()
    main(arguments)
