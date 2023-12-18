import os

from conan.api.output import ConanOutput
from conan.internal.cache.home_paths import HomePaths
from conans.client.cache.cache import ClientCache
from conans.client.graph.proxy import ConanProxy
from conans.client.graph.python_requires import PyRequireLoader
from conans.client.graph.range_resolver import RangeResolver
from conans.client.hook_manager import HookManager
from conans.client.loader import ConanFileLoader, load_python_file
from conans.client.remote_manager import RemoteManager
from conans.client.rest.auth_manager import ConanApiAuthManager
from conans.client.rest.conan_requester import ConanRequester
from conans.client.rest.rest_client import RestApiClientFactory


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
    def __init__(self, requester, cmd_wrapper, global_conf, cache):
        self.requester = requester
        self.cmd_wrapper = cmd_wrapper
        self.global_conf = global_conf
        self.cache = cache


class ConanApp(object):
    def __init__(self, cache_folder, global_conf):
        self._configure(global_conf)
        self.cache_folder = cache_folder
        self.cache = ClientCache(self.cache_folder, global_conf)

        home_paths = HomePaths(self.cache_folder)
        self.hook_manager = HookManager(home_paths.hooks_path)

        # Wraps an http_requester to inject proxies, certs, etc
        self.requester = ConanRequester(global_conf, cache_folder)
        # To handle remote connections
        rest_client_factory = RestApiClientFactory(self.requester, global_conf)
        # Wraps RestApiClient to add authentication support (same interface)
        auth_manager = ConanApiAuthManager(rest_client_factory, self.cache, global_conf)
        # Handle remote connections
        self.remote_manager = RemoteManager(self.cache, auth_manager)

        self.proxy = ConanProxy(self)
        self.range_resolver = RangeResolver(self, global_conf)

        self.pyreq_loader = PyRequireLoader(self, global_conf)
        cmd_wrap = CmdWrapper(home_paths.wrapper_path)
        conanfile_helpers = ConanFileHelpers(self.requester, cmd_wrap, global_conf, self.cache)
        self.loader = ConanFileLoader(self.pyreq_loader, conanfile_helpers)

    @staticmethod
    def _configure(global_conf):
        legacy_warnings_as_errors_bool = global_conf.get("core:warnings_as_errors", None, check_type=bool)
        if legacy_warnings_as_errors_bool is not None:
            # Print this before setting the warnings as errors,
            # else only this will be printed and Conan will exit
            ConanOutput().warning("Boolean 'core:warnings_as_errors' key is deprecated, "
                                  "use a list of patterns instead, e.g. ['*'] to treat all warnings as errors",
                                  warn_tag="deprecated")
            ConanOutput.set_warnings_as_errors(["*"] if legacy_warnings_as_errors_bool else [])
        else:
            ConanOutput.set_warnings_as_errors(global_conf.get("core:warnings_as_errors",
                                                               default=[], check_type=list))
        ConanOutput.define_silence_warnings(global_conf.get("core:skip_warnings",
                                                            default=[], check_type=list))
