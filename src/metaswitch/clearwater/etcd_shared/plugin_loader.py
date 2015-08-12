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
    files = os.listdir(dir)
    plugins = []
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
