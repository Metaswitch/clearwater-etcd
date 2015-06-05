# Project Clearwater - IMS in the Cloud
# Copyright (C) 2015 Metaswitch Networks Ltd
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

from metaswitch.common.pdlogs import PDLog

STARTUP = PDLog(
    number=PDLog.CL_CONFIG_MGR_ID+1,
    desc="clearwater-config-manager has started.",
    cause="The application is starting.",
    effect="Normal.",
    action="None.",
    priority=PDLog.LOG_NOTICE)
EXITING = PDLog(
    number=PDLog.CL_CONFIG_MGR_ID+2,
    desc="clearwater-config-manager is exiting.",
    cause="The application is exiting.",
    effect="Configuration management services are no longer available.",
    action="This occurs normally when the application is stopped. Wait for monit "+\
      "to restart the application.",
    priority=PDLog.LOG_ERR)
EXITING_BAD_CONFIG = PDLog(
    number=PDLog.CL_CONFIG_MGR_ID+3,
    desc="clearwater-config-manager is exiting due to bad configuration.",
    cause="clearwater-config-manager was started with incorrect configuration.",
    effect="Configuration management services are no longer available.",
    action="Verify that the configuration files in /etc/clearwater/ are correct "+\
      "according to the documentation.",
    priority=PDLog.LOG_ERR)
FILE_CHANGED = PDLog(
    number=PDLog.CL_CONFIG_MGR_ID+4,
    desc="A shared configuration file has been changed.",
    cause="The shared state of {filename} has changed.",
    effect="Normal.",
    action="None.",
    priority=PDLog.LOG_NOTICE)

NO_SHARED_CONFIG_ALARM = PDLog(
    number=PDLog.CL_CONFIG_MGR_ID+5,
    desc="This node has no shared config.",
    cause="This node has not yet retrieved its shared config.",
    effect="This node will alarm until it retrieves shared config.",
    action="Wait for this node to retrieve /etc/clearwater/shared_config. If this "+\
    "does not happen, ensure that clearwater-etcd and clearwater-config-manager "+\
    "have started up, and fix any other errors relating to them.",
    priority=PDLog.LOG_ERR)
