# Project Clearwater - IMS in the Cloud
# Copyright (C) 2016 Metaswitch Networks Ltd
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

import os
import sys
import json
import difflib
import requests
import syslog
import codecs

def main():
    '''
    Print a readable diff of changes between etcd's shared_config and a newer
    local copy, and log to syslog.
    '''

    # URL of shared_config etcd key
    url = sys.argv[1]

    old_config_lines = []
    new_config_lines = []

    try:
        # Get the new version of shared config from file, and the old version
        # from etcd. If either of these fail, bail out of trying to log the
        # the changes, and let upload_shared_config handle the errors. The
        # exception to this is when the returned data from etcd doesn't have the
        # right format; this is likely because the shared config key doesn't
        # exist yet (and if it's something more complicated then again
        # upload_shared_config can handle it).
        with codecs.open("/etc/clearwater/shared_config", "r", encoding='utf-8') as ifile:
            new_config_lines = ifile.read().splitlines()

        # Ensure that the text we get back from the request is encoded correctly
        # so that the comparison between old and new config works correctly
        r = requests.get(url)
        r.encoding = "utf-8"
        jsonstr = r.text

        try:
            # etcd returns JSON; the shared_config is in node.value.
            old_config_lines = json.loads(jsonstr)["node"]["value"].splitlines()
        except KeyError:
            pass
    except Exception:
        return

    # We're looking to log meaningful configuration changes, so sort the lines to
    # ignore changes in line ordering
    new_config_lines.sort()
    old_config_lines.sort()
    difflines = list(difflib.ndiff(old_config_lines, new_config_lines))

    # Pull out nonempty diff lines prefixed by "- "
    deletions = [line[2:] for line in difflines if line.startswith("- ") and len(line) > 2]
    # "Concatenate", "like", "this"
    deletions_str = ", ".join(['"' + line + '"' for line in deletions])

    additions = [line[2:] for line in difflines if line.startswith("+ ") and len(line) > 2]
    additions_str = ", ".join(['"' + line + '"' for line in additions])

    # We'll be running as root, but SUDO_USER pulls out the user who invoked sudo
    username = os.environ['SUDO_USER']

    if additions or deletions:
        logstr = "Configuration file change: shared_config was modified by user {}. ".format(username)
        if deletions:
            logstr += "Lines removed: "
            logstr += deletions_str + ". "
        if additions:
            logstr += "Lines added: "
            logstr += additions_str + "."

        # Force encoding so logstr prints and syslogs nicely
        logstr = logstr.encode("utf-8")

        # Print changes to console so the user can do a sanity check
        print logstr

        # Log the changes
        syslog.openlog("audit-log", syslog.LOG_PID)
        syslog.syslog(syslog.LOG_NOTICE, logstr)
        syslog.closelog()
    else:
        print "No changes detected in shared configuration file"

main()
