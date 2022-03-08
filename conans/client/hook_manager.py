import os
from collections import defaultdict
from threading import Lock

from conans.cli.output import ScopedOutput, ConanOutput
from conans.client.loader import load_python_file
from conans.errors import ConanException, NotFoundException

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

    def __init__(self, hooks_folder, hook_names):
        self._hooks_folder = hooks_folder
        self._hook_names = hook_names
        self.hooks = defaultdict(list)
        self._output = ConanOutput()
        self._mutex = Lock()

    def execute(self, method_name, **kwargs):
        # It is necessary to protect the lazy loading of hooks with a mutex, because it can be
        # concurrent (e.g. upload --parallel)
        # TODO: This reads a bit insane, simplify it?
        self._mutex.acquire()
        try:
            if not self.hooks:
                self.load_hooks()
        finally:
            self._mutex.release()

        assert method_name in valid_hook_methods, \
            "Method '{}' not in valid hooks methods".format(method_name)
        for name, method in self.hooks[method_name]:
            try:
                scoped_output = ScopedOutput("[HOOK - %s] %s()" % (name, method_name), self._output)
                method(output=scoped_output, **kwargs)
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
            hook, _ = load_python_file(hook_path)
            for method in valid_hook_methods:
                hook_method = getattr(hook, method, None)
                if hook_method:
                    self.hooks[method].append((hook_name, hook_method))
        except NotFoundException:
            self._output.warning("Hook '%s' not found in %s folder. Please remove hook from conan.conf "
                             "or include it inside the hooks folder." % (hook_name,
                                                                         self._hooks_folder))
        except Exception as e:
            raise ConanException("Error loading hook '%s': %s" % (hook_path, str(e)))
