import imp
import os


def load_plugins_in_dir(dir, config):
    """Loads plugins by:
        - looking for all .py files in the given directory
        - calling their load_as_plugin() function, passing 'config'
        - returning a list containing the return values of all load_as_plugin()
        calls
        """
    files = os.listdir(dir)
    plugins = []
    for filename in files:
        module_name, suffix = filename.split(".")
        if suffix == "py":
            file, pathname, description = imp.find_module(module_name, [dir])
            if file:
                mod = imp.load_module(module_name, file, pathname, description)
                if hasattr(mod, "load_as_plugin"):
                    plugins.append(mod.load_as_plugin(config))
    return plugins
