import os

from conans.cli.output import ConanOutput
from conans.client.loader import load_python_file
from conans.errors import ConanException

valid_hook_methods = ["pre_export", "post_export",
                      "pre_source", "post_source",
                      "pre_build", "post_build",
                      "pre_package", "post_package",
                      "pre_package_info", "post_package_info"]


class HookManager:

    def __init__(self, hooks_folder):
        self._hooks_folder = hooks_folder
        self.hooks = {}
        self._load_hooks()  # A bit dirty, but avoid breaking tests

    def execute(self, method_name, **kwargs):
        assert method_name in valid_hook_methods, \
            "Method '{}' not in valid hooks methods".format(method_name)
        hooks = self.hooks.get(method_name)
        if hooks is None:
            return
        for name, method in hooks:
            try:
                scoped_output = ConanOutput(scope="[HOOK - %s] %s()" % (name, method_name))
                method(output=scoped_output, **kwargs)
            except Exception as e:
                raise ConanException("[HOOK - %s] %s(): %s" % (name, method_name, str(e)))

    def _load_hooks(self):
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
                    self.hooks.setdefault(method, []).append((hook_name, hook_method))
        except Exception as e:
            raise ConanException("Error loading hook '%s': %s" % (hook_path, str(e)))
