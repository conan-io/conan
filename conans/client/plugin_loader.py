import traceback
from importlib.machinery import SourceFileLoader
import inspect
import os
import sys
import uuid

from conans.errors import ConanException, NotFoundException
from conans.tools import chdir


def execute_plugins_method(method_name, plugins_folder, plugin_names, conanfile, conanfile_content,
                           output):
    for plugin_name in plugin_names:
        plugin = load_plugin(plugins_folder, plugin_name, conanfile, conanfile_content, output)
        try:
            method = getattr(plugin, method_name)
            method()
        except AttributeError:
            print("KK")
            pass
        except Exception as e:
            raise ConanException("[PLUGIN: %s.%s()] %s\n%s" % (plugin_name, method_name, e,
                                                               traceback.format_exc()))


def load_plugin(plugins_folder, plugin_name, conanfile, conanfile_content, output):
    filename = "%s.py" % plugin_name
    plugin_path = os.path.join(plugins_folder, filename)
    loaded, filename = _parse_file(plugin_path)
    try:
        plugin = _parse_module(loaded, filename)
        return plugin(conanfile, conanfile_content, output)
    except Exception as e:  # re-raise with file name
        raise ConanException("Error loading plugin '%s': %s" % (plugin_path, str(e)))


def _parse_module(plugin_module, filename):
    """ Parses a python in-memory module, to extract the classes, mainly the main
    class defining the Recipe, but also process possible existing generators
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


def _parse_file(plugin_path):
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
            loaded = SourceFileLoader(filename, plugin_path).load_module()
            # loaded = imp.load_source(filename, plugin_path) # TODO: needed for python 2?
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

    def __init__(self, conanfile, conanfile_content, output):
        self.conanfile = conanfile
        self.conanfile_content = conanfile_content
        self.output = output
