import os

from conan.internal.api.local.editable import EditablePackages
from conan.internal.cache.cache import PkgCache
from conan.internal.model.conf import ConfDefinition
from conan.internal.graph.proxy import ConanProxy
from conan.internal.graph.python_requires import PyRequireLoader
from conan.internal.graph.range_resolver import RangeResolver
from conan.internal.loader import ConanFileLoader, load_python_file
from conan.internal.rest.remote_manager import RemoteManager


class CmdWrapper:
    def __init__(self, wrapper):
        if os.path.isfile(wrapper):
            mod, _ = load_python_file(wrapper)
            self._wrapper = mod.cmd_wrapper
        else:
            self._wrapper = None

    def wrap(self, cmd, conanfile, **kwargs):
        if self._wrapper is None:
            return cmd
        return self._wrapper(cmd, conanfile=conanfile, **kwargs)


class ConanFileHelpers:
    def __init__(self, requester, cmd_wrapper, global_conf, cache, home_folder, conan_api,
                 flags_map=None):
        self.requester = requester
        self.cmd_wrapper = cmd_wrapper
        self.global_conf = global_conf
        self.cache = cache
        self.home_folder = home_folder
        self.conan_api = conan_api  # Might be None for local-recipes-index
        self.flags_map = flags_map


class LocalRecipesIndexApp:
    """
    Simplified one, without full API, for the LocalRecipesIndex. Only publicly used fields are:
    - cache
    - loader (for the export phase of local-recipes-index)
    The others are internally use by other collaborators
    """
    def __init__(self, cache_folder):
        self.global_conf = ConfDefinition()
        self.cache = PkgCache(cache_folder, self.global_conf)
        self.remote_manager = RemoteManager(self.cache, auth_manager=None, home_folder=cache_folder)
        editable_packages = EditablePackages()
        self.proxy = ConanProxy(self.cache, self.remote_manager, editable_packages)
        self.range_resolver = RangeResolver(self.cache, self.remote_manager, self.global_conf,
                                            editable_packages)
        pyreq_loader = PyRequireLoader(self.proxy, self.range_resolver, self.global_conf)
        helpers = ConanFileHelpers(None, CmdWrapper(""), self.global_conf, self.cache, cache_folder, None)
        self.loader = ConanFileLoader(pyreq_loader, helpers)
