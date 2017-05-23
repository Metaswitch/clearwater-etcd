# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.

from metaswitch.common.pdlogs import PDLog

STARTUP = PDLog(
    number=PDLog.CL_QUEUE_MGR_ID+1,
    desc="clearwater-queue-manager has started.",
    cause="The application is starting.",
    effect="Normal.",
    action="None.",
    priority=PDLog.LOG_NOTICE)
EXITING = PDLog(
    number=PDLog.CL_QUEUE_MGR_ID+2,
    desc="clearwater-queue-manager is exiting.",
    cause="The application is exiting.",
    effect="Configuration synchronization services are no longer available.",
    action="This occurs normally when the application is stopped. Wait for monit "+\
      "to restart the application.",
    priority=PDLog.LOG_ERR)
EXITING_BAD_CONFIG = PDLog(
    number=PDLog.CL_QUEUE_MGR_ID+3,
    desc="clearwater-queue-manager is exiting due to bad configuration.",
    cause="clearwater-queue-manager was started with incorrect configuration.",
    effect="Configuration synchronization services are no longer available.",
    action="Verify that the configuration files in /etc/clearwater/ are correct "+\
      "according to the documentation.",
    priority=PDLog.LOG_ERR)
