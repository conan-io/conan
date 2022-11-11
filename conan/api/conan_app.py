import os

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
    def __init__(self, cache):
        wrapper = os.path.join(cache.cache_folder, "extensions", "plugins", "cmd_wrapper.py")
        if os.path.isfile(wrapper):
            mod, _ = load_python_file(wrapper)
            self._wrapper = mod.cmd_wrapper
        else:
            self._wrapper = None

    def wrap(self, cmd):
        if self._wrapper is None:
            return cmd
        return self._wrapper(cmd)


class ConanFileHelpers:
    def __init__(self, requester, cmd_wrapper):
        self.requester = requester
        self.cmd_wrapper = cmd_wrapper


class ConanApp(object):
    def __init__(self, cache_folder):

        self.cache_folder = cache_folder
        self.cache = ClientCache(self.cache_folder)

        self.hook_manager = HookManager(self.cache.hooks_path)
        # Wraps an http_requester to inject proxies, certs, etc
        self.requester = ConanRequester(self.cache.new_config)
        # To handle remote connections
        rest_client_factory = RestApiClientFactory(self.requester, self.cache.new_config)
        # Wraps RestApiClient to add authentication support (same interface)
        auth_manager = ConanApiAuthManager(rest_client_factory, self.cache)
        # Handle remote connections
        self.remote_manager = RemoteManager(self.cache, auth_manager, self.hook_manager)

        self.proxy = ConanProxy(self)
        self.range_resolver = RangeResolver(self)

        self.pyreq_loader = PyRequireLoader(self.proxy, self.range_resolver)
        cmd_wrap = CmdWrapper(self.cache)
        conanfile_helpers = ConanFileHelpers(self.requester, cmd_wrap)
        self.loader = ConanFileLoader(self.pyreq_loader, conanfile_helpers)
