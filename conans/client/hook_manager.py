import os
import sys
import traceback
import uuid
from collections import defaultdict
from threading import Lock

from conans.client.output import ScopedOutput
from conans.client.tools.files import chdir
from conans.errors import ConanException, NotFoundException
from conans.util.files import save

attribute_checker_hook = """
def pre_export(output, conanfile, conanfile_path, reference, **kwargs):
    # Check basic meta-data
    for field in ["url", "license", "description"]:
        field_value = getattr(conanfile, field, None)
        if not field_value:
            output.warn("Conanfile doesn't have '%s'. It is recommended to add it as attribute"
                        % field)
"""

valid_hook_methods = ["pre_export", "post_export",
                      "pre_source", "post_source",
                      "pre_build", "post_build",
                      "pre_package", "post_package",
                      "pre_upload", "post_upload",
                      "pre_upload_recipe", "post_upload_recipe",
                      "pre_upload_package", "post_upload_package",
                      "pre_download", "post_download",
                      "pre_download_recipe", "post_download_recipe",
                      "pre_download_package", "post_download_package",
                      "pre_package_info", "post_package_info"]


class HookManager(object):

    def __init__(self, hooks_folder, hook_names, output):
        self._hooks_folder = hooks_folder
        self._hook_names = hook_names
        self.hooks = defaultdict(list)
        self.output = output
        self._attribute_checker_path = os.path.join(self._hooks_folder, "attribute_checker.py")
        self._mutex = Lock()

    def execute(self, method_name, **kwargs):
        # It is necessary to protect the lazy loading of hooks with a mutex, because it can be
        # concurrent (e.g. upload --parallel)
        self._mutex.acquire()
        try:
            if not os.path.exists(self._attribute_checker_path):
                save(self._attribute_checker_path, attribute_checker_hook)
            if not self.hooks:
                self.load_hooks()
        finally:
            self._mutex.release()

        assert method_name in valid_hook_methods, \
            "Method '{}' not in valid hooks methods".format(method_name)
        for name, method in self.hooks[method_name]:
            try:
                output = ScopedOutput("[HOOK - %s] %s()" % (name, method_name), self.output)
                method(output=output, **kwargs)
            except Exception as e:
                raise ConanException("[HOOK - %s] %s(): %s" % (name, method_name, str(e)))

    def load_hooks(self):
        for name in self._hook_names:
            self._load_hook(name)

    def _load_hook(self, hook_name):
        if not hook_name.endswith(".py"):
            hook_name = "%s.py" % hook_name
        hook_path = os.path.normpath(os.path.join(self._hooks_folder, hook_name))
        try:
            hook = HookManager._load_module_from_file(hook_path)
            for method in valid_hook_methods:
                hook_method = getattr(hook, method, None)
                if hook_method:
                    self.hooks[method].append((hook_name, hook_method))
        except NotFoundException:
            self.output.warn("Hook '%s' not found in %s folder. Please remove hook from conan.conf "
                             "or include it inside the hooks folder." % (hook_name,
                                                                         self._hooks_folder))
        except Exception as e:
            raise ConanException("Error loading hook '%s': %s" % (hook_path, str(e)))

    @staticmethod
    def _load_module_from_file(hook_path):
        """ From a given path, obtain the in memory python import module
        """
        if not os.path.exists(hook_path):
            raise NotFoundException
        filename = os.path.splitext(os.path.basename(hook_path))[0]
        current_dir = os.path.dirname(hook_path)

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
                        try:
                            # Most modules will have __file__ != None
                            folder = os.path.dirname(module.__file__)
                        except (AttributeError, TypeError):
                            # But __file__ might not exist or equal None
                            # Like some builtins and Namespace packages py3
                            folder = module.__path__._path[0]
                    except AttributeError:  # In case the module.__path__ doesn't exist
                        pass
                    else:
                        if folder.startswith(current_dir):
                            module = sys.modules.pop(added)
                            sys.modules["%s.%s" % (module_id, added)] = module
        except Exception:
            trace = traceback.format_exc().split('\n')
            raise ConanException("Unable to load Hook in %s\n%s" % (hook_path,
                                                                    '\n'.join(trace[3:])))
        finally:
            sys.dont_write_bytecode = False
            sys.path.pop()
        return loaded
