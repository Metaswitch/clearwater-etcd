# Project Clearwater - IMS in the Cloud
# Copyright (C) 2016  Metaswitch Networks Ltd
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version, along with the "Special Exception" for use of
# the program along with SSL, set forth below. This program is distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details. You should have received a copy of the GNU General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.
#
# The author can be reached by email at clearwater@metaswitch.com or by
# post at Metaswitch Networks Ltd, 100 Church St, Enfield EN2 6BQ, UK
#
# Special Exception
# Metaswitch Networks Ltd  grants you permission to copy, modify,
# propagate, and distribute a work formed by combining OpenSSL with The
# Software, or a work derivative of such a combination, even if such
# copying, modification, propagation, or distribution would otherwise
# violate the terms of the GPL. You must comply with the GPL in all
# respects for all of the code used other than OpenSSL.
# "OpenSSL" means OpenSSL toolkit software distributed by the OpenSSL
# Project and licensed under the OpenSSL Licenses, or a work based on such
# software and licensed under the OpenSSL Licenses.
# "OpenSSL Licenses" means the OpenSSL License and Original SSLeay License
# under which the OpenSSL Project distributes the OpenSSL toolkit software,
# as those licenses appear in the file LICENSE-OPENSSL.

from metaswitch.clearwater.etcd_shared.plugin_utils import run_command, safely_write
import logging
import os
import re
import shutil
import subprocess

# Not sure if we need the non-CC packages here
PACKAGES = "cassandra clearwater-cassandra homestead-cassandra homestead-prov-cassandra homer-cassandra memento-cassandra"
SOURCES_FILE = "/etc/apt/sources.list.d/clearwater.list"
TEMP_SOURCES_FILE = "/tmp/clearwater.list"
VERSION_FILE = "/etc/clearwater/cassandra_version"

_log = logging.getLogger("cassandra_upgrade_plugin")

def get_cassandra_version():
    version = ""
    nodetool_process = subprocess.Popen("/usr/share/clearwater/bin/run-in-signaling-namespace nodetool version",
                                        stdout=subprocess.PIPE,
                                        shell=True)

    # The output of nodetool version is like "ReleaseVersion: 2.0.14"
    version_regex = "ReleaseVersion: (.*)$"
    for line in nodetool_process.stdout:
        line = line.strip()
        m = re.match(version_regex, line)
        if m:
            version = m.group(1)
            break

    return version

# Attempts the Cassandra upgrade.
# Returns True if the upgrade succeeded or no upgrade was necessary.
# Returns False if not.
def do_upgrade():
    # First, read the desired cassandra version and check we need to upgrade
    new_version = ""
    repo_dir = ""
    with open(VERSION_FILE, "r") as version_file:
        for line in version_file:
            line = line.strip()
            if line.startswith("desired_version"):
                # The version is specified as desired_version=CCxxxxx_cass<cass_version>
                split_line = line.split("=")
                if len(split_line) == 2:
                    #  The repo_dir is everything after the equals
                    repo_dir = split_line[1].strip()

                    # The cassandra version is everything after the "cass"
                    split_repo_dir = repo_dir.split("cass")
                    if len(split_repo_dir) == 2:
                        new_version = split_repo_dir[1].strip()
            break

    if new_version == "":
        _log.error("Unable to read desired Cassandra version from {0}".format(VERSION_FILE))
        return False

    old_version = get_cassandra_version()
    if old_version == "":
        _log.error("Unable to get current Cassandra version")
        return False

    if new_version == old_version:
        _log.info("Current version equal to desired version: {0}; nothing to do".format(new_version))
        return True

    _log.info("Upgrading Cassandra from version {0} to version {1}".format(old_version, new_version))

    if run_command("/usr/share/clearwater/bin/run-in-signaling-namespace nodetool upgradesstables"):
        _log.error("Unable to upgrade sstables")
        return False

    _log.info("Updating cassandra repo")

    # Create a backup of the sources list file to roll back to if necessary
    shutil.copyfile(SOURCES_FILE, TEMP_SOURCES_FILE)

    # The clearwater sources list should include a single source. Update it
    # to point to the new repo directory
    new_repo = ""
    with open(SOURCES_FILE, "r") as file:
        for line in file:
            if line.startswith("deb"):
                split_line = line.split(" ")
                if len(split_line) > 2:
                    old_repo = split_line[1]

                    # If old_repo has a trailing slash, remove it
                    if old_repo.endswith("/"):
                        old_repo = old_repo[:-1]

                    # Check that the Clearwater version isn't changing
                    split_repo = old_repo.split("/")

                    old_cc_version = split_repo[-1].split("cass")[0]
                    new_cc_version = repo_dir.split("cass")[0]

                    if old_cc_version != new_cc_version:
                        _log.error("Can't upgrade CC and Cassandra at the same time")
                    else:
                        # Rebuild the string, replacing the final path segment with
                        # the new repo directory
                        path_list = split_repo[:-1]
                        path_list.append(repo_dir)
                        new_repo = "/".join(path_list)
                break

    if new_repo == "":
        _log.error("Aborting upgrade")
        return False

    # Add the new Cassandra repo to the sources, then write back
    new_sources = "deb {0} binary/\n".format(new_repo)
    safely_write(SOURCES_FILE, new_sources)

    # Now, check that we can find the repo and that upgrade will work by doing a dry-run
    if run_command("sudo apt-get update " +
                   "-o Dir::Etc::sourcelist=\"sources.list.d/clearwater.list\" " +
                   "-o Dir::Etc::sourceparts=\"-\" " +
                   "-o APT::Get::List-Cleanup=\"0\""):
        _log.error("Unable to contact repo {0}".format(new_repo))
        shutil.move(TEMP_SOURCES_FILE, SOURCES_FILE)
        return False

    if run_command("sudo apt-get install --only-upgrade --dry-run " + PACKAGES + " "
                   "-o Dir::Etc::sourcelist=\"sources.list.d/clearwater.list\" " +
                   "-o Dir::Etc::sourceparts=\"-\" " +
                   "-o APT::Get::List-Cleanup=\"0\""):
        _log.error("Will not be able to upgrade Cassandra packages")
        shutil.move(TEMP_SOURCES_FILE, SOURCES_FILE)
        return False

    # Start performing the uprade
    _log.info("Draining node")
    if run_command("/usr/share/clearwater/bin/run-in-signaling-namespace nodetool drain"):
        _log.error("Unable to drain node")
        shutil.move(TEMP_SOURCES_FILE, SOURCES_FILE)
        return False

    if run_command("sudo monit stop cassandra_process"):
        _log.error("Unable to stop cassandra process")
        shutil.move(TEMP_SOURCES_FILE, SOURCES_FILE)
        return False

    _log.info("Upgrading Cassandra")
    if run_command("sudo apt-get install --yes --force-yes --only-upgrade " + PACKAGES + " "
                   "-o Dir::Etc::sourcelist=\"sources.list.d/clearwater.list\" " +
                   "-o Dir::Etc::sourceparts=\"-\" " +
                   "-o APT::Get::List-Cleanup=\"0\""):
        _log.error("Unable to upgrade Cassandra packages")
        shutil.move(TEMP_SOURCES_FILE, SOURCES_FILE)
        return False

    # We're not going to roll back the sources file at this point, so delete the backup
    os.remove(TEMP_SOURCES_FILE)

    run_command("sudo monit start cassandra_process")

    # Wait for cassandra to restart
    if run_command("/usr/share/clearwater/clearwater-queue-manager/scripts/check_node_health.py"):
        _log.error("Unable to restart cassandra afer upgrade")
        return False

    _log.info("Upgrading sstables")
    if run_command("/usr/share/clearwater/bin/run-in-signaling-namespace nodetool upgradesstables"):
        _log.error("Unable to upgrade sstables")
        return False

    return True

