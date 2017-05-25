# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.
from metaswitch.clearwater.config_manager.plugin_base import ConfigPluginBase
from mock import MagicMock

class TestPlugin(ConfigPluginBase):
    def __init__(self):
        self._on_config_changed = MagicMock()

    def key(self):
        return "test"

    def file(self):
        pass

    def status(self, value):
        pass

    def default_value(self):
        return "default_value"

    def on_config_changed(self, value, alarm):
        return self._on_config_changed(value, alarm)
