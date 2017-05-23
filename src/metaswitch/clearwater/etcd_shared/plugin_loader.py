# Copyright (C) Metaswitch Networks 2017
# If license terms are provided to you in a COPYING file in the root directory
# of the source code repository by which you are accessing this code, then
# the license outlined in that COPYING file applies to your use.
# Otherwise no rights are granted except for those provided to you by
# Metaswitch Networks in a separate written agreement.


import logging
import imp
import os

_log = logging.getLogger("etcd_shared.plugin_loader")

def load_plugins_in_dir(dir, params=None):
    """Loads plugins by:
        - looking for all .py files in the given directory
        - calling their load_as_plugin() function
        - returning a list containing the return values of all load_as_plugin()
        calls
        """
    plugins = []
    if os.path.isdir(dir):
        files = os.listdir(dir)
        for filename in files:
            _log.info("Inspecting {}".format(filename))
            module_name, suffix = os.path.splitext(filename)
            if suffix == ".py":
                file, pathname, description = imp.find_module(module_name, [dir])
                if file:
                    mod = imp.load_module(module_name, file, pathname, description)
                    if hasattr(mod, "load_as_plugin"):
                        plugin = mod.load_as_plugin(params)
                        _log.info("Loading {}".format(filename))
                        if plugin is not None:
                            _log.info("Loaded {} successfully".format(filename))
                            plugins.append(plugin)
                        else: # pragma : no cover
                            _log.info("{} did not load (load_as_plugin returned None)".format(filename))
    return plugins
