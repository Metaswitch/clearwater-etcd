import imp
import os

SECRET_VALUE = 7


def load_plugins_in_dir(dir):
  files = os.listdir(dir)
  for filename in files:
    module_name, suffix = filename.split(".")
    if suffix == "py":
      file, pathname, description = imp.find_module(module_name, [dir])
      if file:
        mod = imp.load_module(module_name, file, pathname, description)
        if hasattr(mod, "load_as_plugin"):
          mod.load_as_plugin()

if __name__ == "__main__":
  load_plugins_in_dir("/home/vagrant/python_plugins/")
