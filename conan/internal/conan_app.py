import os

from conan.internal.api.local.editable import EditablePackages
from conan.internal.cache.cache import PkgCache
from conan.internal.cache.home_paths import HomePaths
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
    def __init__(self, requester, cmd_wrapper, global_conf, cache, home_folder, conan_api):
        self.requester = requester
        self.cmd_wrapper = cmd_wrapper
        self.global_conf = global_conf
        self.cache = cache
        self.home_folder = home_folder
        self.conan_api = conan_api  # Might be None for local-recipes-index


class ConanBasicApp:
    def __init__(self, conan_api):
        """ Needs:
        - Global configuration
        - Cache home folder
        """
        # TODO: Remove this global_conf from here
        global_conf = conan_api._api_helpers.global_conf  # noqa
        # TODO: Temporary while refactoring, remove i nthe future
        self._cache = conan_api._api_helpers.cache # noqa
        self._remote_manager = conan_api._api_helpers.remote_manager  # noqa
        self._global_conf = global_conf
        self.cache_folder = conan_api.home_folder
        global_editables = conan_api.local.editable_packages
        ws_editables = conan_api.workspace.packages()
        self.editable_packages = global_editables.update_copy(ws_editables)


class ConanApp(ConanBasicApp):
    def __init__(self, conan_api):
        """ Needs:
        - LocalAPI to read editable packages
        """
        super().__init__(conan_api)
        legacy_update = self._global_conf.get("core:update_policy", choices=["legacy"])
        self.proxy = ConanProxy(self._cache, self._remote_manager, self.editable_packages,
                                legacy_update=legacy_update)
        self.range_resolver = RangeResolver(self._cache, self._remote_manager, self._global_conf,
                                            self.editable_packages)
        cmd_wrap = CmdWrapper(HomePaths(self.cache_folder).wrapper_path)
        requester = conan_api._api_helpers.requester  # noqa
        conanfile_helpers = ConanFileHelpers(requester, cmd_wrap, self._global_conf, self._cache,
                                             self.cache_folder, conan_api)
        pyreq_loader = PyRequireLoader(self.proxy, self.range_resolver, self._global_conf)
        self.loader = ConanFileLoader(pyreq_loader, conanfile_helpers)


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
