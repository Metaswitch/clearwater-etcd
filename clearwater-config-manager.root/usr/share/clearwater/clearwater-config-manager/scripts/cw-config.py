# Copyright (C) Metaswitch Networks 2016
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

# Constants
SHARED_CONFIG_PATH = "/etc/clearwater/shared_config"
DOWNLOADED_CONFIG_PATH = "/var/tmp/config"

# Error messages
MODIFIED_WHILE_EDITING = """Another user has modified the configuration since
cw-download_shared_config was last run. Please download the latest version of
shared config, re-apply the changes and try again."""


def main(args):
    """
    Main entry point for script.
    """
    # Set up logging

    # Regardless of passed arguments we want to delete outdated config to not
    # leave unused files on disk.
    delete_outdated_config_files()

    if args["action"] == "download":
        try:
            download_config()
        except:
            pass

    if args["action"] == "upload":
        try:
            validate_config()
            upload_config()
        except:
            pass


def parse_arguments():
    """
    Parse the arguments passed to the script.
    :return:
    """
    pass


def delete_outdated_config_files():
    """
    Deletes all config files in any subfolder of DOWNLOADED_CONFIG_PATH that is
    older than 30 days.
    :return:
    """
    pass


def download_config():
    """
    Downloads the config from etcd and saves a copy to
    DOWNLOADED_CONFIG_PATH/<USER_NAME>.
    :return:
    """
    pass


def validate_config():
    """
    Validates the config.
    :return:
    """
    pass


def upload_config():
    """
    Uploads the config from DOWNLOADED_CONFIG_PATH/<USER_NAME> to etcd.
    .
    :return:
    """
    pass


def get_user_name():
    """
    Returns the current user name.
    :return:
    """
    pass

# Call main function if script is executed stand-alone
if __name__ == "__main__":
    arguments = parse_arguments()
    main(arguments)
