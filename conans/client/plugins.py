import traceback
import inspect
import os
import sys
import uuid

from past.builtins import execfile

from conans.client.output import ScopedOutput
from conans.errors import ConanException, NotFoundException
from conans.tools import chdir


class PluginManager(object):

    def __init__(self, plugins_folder, plugin_names, output):
        self._plugins_folder = plugins_folder
        self._plugin_names = plugin_names
        self.loaded_plugins = []
        self.plugins = None
        self.output = output
        self._last_method_executed = None

    def load_plugins(self):
        for name in self._plugin_names:
            if name and name not in [file[:-3] for file in os.listdir(self._plugins_folder)]:
                self.output.warn("Plugin '%s' not found in %s folder. Please remove plugin "
                                 "from conan.conf or include it inside the plugins folder."
                                 % (name, self._plugins_folder))
                continue
            plugin = self.load_plugin(name)
            self.loaded_plugins.append(plugin)

    def initialize_plugins(self, conanfile=None, conanfile_path=None, remote_name=None):
        if not self.plugins:
            self.plugins = [plugin(self.output, conanfile, conanfile_path, remote_name)
                            for plugin in self.loaded_plugins]
        else:
            for plugin in self.plugins:
                if self.output:
                    plugin.output = self.output
                if conanfile:
                    plugin.conanfile = conanfile
                if conanfile_path:
                    plugin.conanfile_path = conanfile_path
                if remote_name:
                    plugin.remote_name = remote_name

    def deinitialize_plugins(self):
        for plugin in self.plugins:
            plugin.conanfile = None
            plugin.conanfile_path = None
            plugin.remote_name = None

    def execute_plugins_method(self, method_name, conanfile=None, conanfile_path=None,
                               remote_name=None):
        if self._last_method_executed:
            if self._last_method_executed.split("_")[:-1] != method_name.split("_"):
                self.deinitialize_plugins()
        self._last_method_executed = method_name
        self.initialize_plugins(conanfile, conanfile_path, remote_name)

        for plugin in self.plugins:
            try:
                method = getattr(plugin, method_name)
                method()
            except NotImplementedError:
                pass
            except Exception as e:
                raise ConanException("[PLUGIN: %s()] %s\n%s" % (method_name, e,
                                                                traceback.format_exc()))

    def load_plugin(self, plugin_name):
        filename = "%s.py" % plugin_name
        plugin_path = os.path.join(self._plugins_folder, filename)
        try:
            loaded, filename = self._parse_file(plugin_path)
            loaded_plugin = self._parse_module(loaded, filename)
            return loaded_plugin
        except Exception as e:  # re-raise with file name
            raise ConanException("Error loading plugin '%s': %s" % (plugin_path, str(e)))

    def _parse_module(self, plugin_module, filename):
        """ Parses a python in-memory module, to extract the classes, mainly the main class defining
        the Plugin
        @param plugin_module: the module to be processed
        @return: the main ConanPlugin class from the module
        """
        result = None
        for name, attr in plugin_module.__dict__.items():
            if name[0] == "_":
                continue
            if (inspect.isclass(attr) and issubclass(attr, ConanPlugin) and attr != ConanPlugin and
                    attr.__dict__["__module__"] == filename):
                if result is None:
                    result = attr
                else:
                    raise ConanException("More than 1 Plugin in the file")

        if result is None:
            raise ConanException("No subclass of ConanPlugin")

        return result

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
                execfile(plugin_path)
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
            import traceback
            trace = traceback.format_exc().split('\n')
            raise ConanException("Unable to load Plugin in %s\n%s" % (plugin_path,
                                                                      '\n'.join(trace[3:])))
        finally:
            sys.path.pop()

        return loaded, filename


class ConanPlugin(object):

    def __init__(self, output, conanfile=None, conanfile_path=None, remote_name=None):
        self.conanfile = conanfile
        self.conanfile_path = conanfile_path
        self._output = ScopedOutput("[PLUGIN - %s]" % self.__class__.__name__, output)
        self.remote_name = remote_name

    @property
    def output(self):
        return self._output

    @output.setter
    def output(self, output):
        self._output = ScopedOutput("[PLUGIN - %s]" % self.__class__.__name__, output)

    def pre_export(self):
        raise NotImplementedError("Implement in subclass")

    def post_export(self):
        raise NotImplementedError("Implement in subclass")

    def pre_source(self):
        raise NotImplementedError("Implement in subclass")

    def post_source(self):
        raise NotImplementedError("Implement in subclass")

    def pre_build(self):
        raise NotImplementedError("Implement in subclass")

    def post_build(self):
        raise NotImplementedError("Implement in subclass")

    def pre_package(self):
        raise NotImplementedError("Implement in subclass")

    def post_package(self):
        raise NotImplementedError("Implement in subclass")

    def pre_upload(self):
        raise NotImplementedError("Implement in subclass")

    def post_upload(self):
        raise NotImplementedError("Implement in subclass")

    def pre_install(self):
        raise NotImplementedError("Implement in subclass")

    def post_install(self):
        raise NotImplementedError("Implement in subclass")

    def pre_download(self):
        raise NotImplementedError("Implement in subclass")

    def post_download(self):
        raise NotImplementedError("Implement in subclass")
