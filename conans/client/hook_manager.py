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

    def __init__(self, hooks_folder):
        self._hooks_folder = hooks_folder
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
        hooks = {}
        for root, dirs, files in os.walk(self._hooks_folder):
            for f in files:
                if f.startswith("hook_") and f.endswith(".py"):
                    hook_path = os.path.join(root, f)
                    name = os.path.relpath(hook_path, self._hooks_folder).replace("\\", "/")
                    hooks[name] = hook_path
        # Load in alphabetical order, just in case the order is important there is a criteria
        # This is difficult to test, apparently in most cases os.walk is alphabetical
        for name, hook_path in sorted(hooks.items()):
            self._load_hook(hook_path, name)

    def _load_hook(self, hook_path, hook_name):
        try:
            hook, _ = load_python_file(hook_path)
            for method in valid_hook_methods:
                hook_method = getattr(hook, method, None)
                if hook_method:
                    self.hooks[method].append((hook_name, hook_method))
        except NotFoundException:
            self._output.warning("Hook '%s' not found in %s folder."
                                 % (hook_name, self._hooks_folder))
        except Exception as e:
            raise ConanException("Error loading hook '%s': %s" % (hook_path, str(e)))
