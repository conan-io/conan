import traceback
import os
import sys
import uuid

from conans.client.output import ScopedOutput
from conans.errors import ConanException, NotFoundException
from conans.tools import chdir


class PluginManager(object):

    def __init__(self, plugins_folder, plugin_names, output):
        self._plugins_folder = plugins_folder
        self._plugin_names = plugin_names
        self.plugins = {}
        self.output = output

    def execute(self, method_name, conanfile=None, conanfile_path=None, **kwargs):
        if not self.plugins:
            self.load_plugins()

        for name, plugin in self.plugins.items():
            try:
                method = getattr(plugin, method_name)
                output = ScopedOutput("[PLUGIN - %s] %s()" % (name, method_name), self.output)
                method(output=output, conanfile=conanfile, conanfile_path=conanfile_path, **kwargs)
            except AttributeError:
                pass
            except Exception as e:
                raise ConanException("[PLUGIN - %s] %s() %s\n%s" % (name, method_name, e,
                                                                    traceback.format_exc()))

    def load_plugins(self):
        for name in self._plugin_names:
            if name and name not in [file[:-3] for file in os.listdir(self._plugins_folder)]:
                self.output.warn("Plugin '%s' not found in %s folder. Please remove plugin "
                                 "from conan.conf or include it inside the plugins folder."
                                 % (name, self._plugins_folder))
                continue
            plugin = self.load_plugin(name)
            self.plugins[name] = plugin

    def load_plugin(self, plugin_name):
        filename = "%s.py" % plugin_name
        plugin_path = os.path.join(self._plugins_folder, filename)
        try:
            loaded_plugin, filename = self._parse_file(plugin_path)
            return loaded_plugin
        except Exception as e:  # re-raise with file name
            raise ConanException("Error loading plugin '%s': %s" % (plugin_path, str(e)))

    def _parse_file(self, plugin_path):
        """ From a given path, obtain the in memory python import module
        """
        if not os.path.exists(plugin_path):
            raise NotFoundException("%s not found!" % plugin_path)

        filename = os.path.splitext(os.path.basename(plugin_path))[0]

        try:
            current_dir = os.path.dirname(plugin_path)
            sys.path.append(current_dir)
            old_modules = list(sys.modules.keys())
            with chdir(current_dir):
                sys.dont_write_bytecode = True
                loaded = __import__(filename)
                sys.dont_write_bytecode = False
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
            sys.path.pop()

        return loaded, filename
