# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

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
