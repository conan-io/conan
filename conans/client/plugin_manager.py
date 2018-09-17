import traceback
import os
import sys
import uuid
from collections import defaultdict

from conans.client.output import ScopedOutput
from conans.errors import ConanException, NotFoundException
from conans.tools import chdir
from conans.util.files import save


attribute_checker_plugin = """
def pre_export(output, conanfile, conanfile_path, reference, **kwargs):
    # Check basic meta-data
    for field in ["url", "license", "description"]:
        field_value = getattr(conanfile, field, None)
        if not field_value:
            output.warn("Conanfile doesn't have '%s'. It is recommended to add it as attribute"
                        % field)
"""

valid_plugin_methods = ["pre_export", "post_export",
                        "pre_source", "post_source",
                        "pre_build", "post_build",
                        "pre_package", "post_package",
                        "pre_upload", "post_upload",
                        "pre_upload_recipe", "post_upload_recipe",
                        "pre_upload_package", "post_upload_package",
                        "pre_download", "post_download",
                        "pre_download_recipe", "post_download_recipe",
                        "pre_download_package", "post_download_package"
                        ]


class PluginManager(object):

    def __init__(self, plugins_folder, plugin_names, output):
        self._plugins_folder = plugins_folder
        self._plugin_names = plugin_names
        self.plugins = defaultdict(list)
        self.output = output

    def create_default_plugins(self):
        attribute_checker_path = os.path.join(self._plugins_folder, "attribute_checker.py")
        save(attribute_checker_path, attribute_checker_plugin)

    def execute(self, method_name, **kwargs):
        if not os.path.exists(os.path.join(self._plugins_folder, "attribute_checker.py")):
            self.create_default_plugins()
        if not self.plugins:
            self.load_plugins()

        assert method_name in valid_plugin_methods
        for name, method in self.plugins[method_name]:
            try:
                output = ScopedOutput("[PLUGIN - %s] %s()" % (name, method_name), self.output)
                method(output, **kwargs)
            except Exception as e:
                raise ConanException("[PLUGIN - %s] %s(): %s\n%s" % (name, method_name, str(e),
                                                                     traceback.format_exc()))

    def load_plugins(self):
        for name in self._plugin_names:
            self.load_plugin(name)

    def load_plugin(self, plugin_name):
        filename = "%s.py" % plugin_name
        plugin_path = os.path.join(self._plugins_folder, filename)
        try:
            plugin = PluginManager._load_module_from_file(plugin_path)
            for method in valid_plugin_methods:
                plugin_method = getattr(plugin, method, None)
                if plugin_method:
                    self.plugins[method].append((plugin_name, plugin_method))
        except NotFoundException:
            self.output.warn("Plugin '%s' not found in %s folder. Please remove plugin "
                             "from conan.conf or include it inside the plugins folder."
                             % (filename, self._plugins_folder))
        except Exception as e:
            raise ConanException("Error loading plugin '%s': %s" % (plugin_path, str(e)))

    @staticmethod
    def _load_module_from_file(plugin_path):
        """ From a given path, obtain the in memory python import module
        """
        if not os.path.exists(plugin_path):
            raise NotFoundException
        filename = os.path.splitext(os.path.basename(plugin_path))[0]
        current_dir = os.path.dirname(plugin_path)

        try:
            sys.path.append(current_dir)
            old_modules = list(sys.modules.keys())
            with chdir(current_dir):
                sys.dont_write_bytecode = True
                loaded = __import__(filename)
            # Put all imported files under a new package name
            module_id = uuid.uuid1()
            added_modules = set(sys.modules).difference(old_modules)
            for added in added_modules:
                module = sys.modules[added]
                if module:
                    try:
                        folder = os.path.dirname(module.__file__)
                    except AttributeError:  # some module doesn't have __file__
                        pass
                    else:
                        if folder.startswith(current_dir):
                            module = sys.modules.pop(added)
                            sys.modules["%s.%s" % (module_id, added)] = module
        except Exception:
            trace = traceback.format_exc().split('\n')
            raise ConanException("Unable to load Plugin in %s\n%s" % (plugin_path,
                                                                      '\n'.join(trace[3:])))
        finally:
            sys.dont_write_bytecode = False
            sys.path.pop()

        return loaded
