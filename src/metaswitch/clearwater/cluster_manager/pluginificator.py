import imp
import os

def load_plugins_in_dir(dir, arbitrary_object):
  files = os.listdir(dir)
  for filename in files:
    module_name, suffix = filename.split(".")
    if suffix == "py":
      file, pathname, description = imp.find_module(module_name, [dir])
      if file:
        mod = imp.load_module(module_name, file, pathname, description)
        if hasattr(mod, "load_as_plugin"):
          mod.load_as_plugin(arbitrary_object)
