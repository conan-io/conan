import conans
from conans.client.cache.cache import ClientCache
from conans.client.graph.graph_binaries import GraphBinariesAnalyzer
from conans.client.graph.graph_manager import GraphManager
from conans.client.graph.proxy import ConanProxy
from conans.client.graph.python_requires import PyRequireLoader
from conans.client.graph.range_resolver import RangeResolver
from conans.client.hook_manager import HookManager
from conans.client.loader import ConanFileLoader
from conans.client.remote_manager import RemoteManager
from conans.client.rest.auth_manager import ConanApiAuthManager
from conans.client.rest.conan_requester import ConanRequester
from conans.client.rest.rest_client import RestApiClientFactory
from conans.client.runner import ConanRunner
from conans.errors import ConanException
from conans.tools import set_global_instances
from conans.util.log import configure_logger


class ConanApp(object):
    def __init__(self, cache_folder):

        self.cache_folder = cache_folder
        self.cache = ClientCache(self.cache_folder)
        self.config = self.cache.config

        # Adjust CONAN_LOGGING_LEVEL with the env readed
        conans.util.log.logger = configure_logger(self.config.logging_level,
                                                  self.config.logging_file)
        conans.util.log.logger.debug("INIT: Using config '%s'" % self.cache.conan_conf_path)

        self.hook_manager = HookManager(self.cache.hooks_path, self.config.hooks)
        # Wraps an http_requester to inject proxies, certs, etc
        self.requester = ConanRequester(self.config)
        # To handle remote connections
        artifacts_properties = self.cache.read_artifacts_properties()
        rest_client_factory = RestApiClientFactory(self.requester, self.config,
                                                   artifacts_properties=artifacts_properties)
        # Wraps RestApiClient to add authentication support (same interface)
        auth_manager = ConanApiAuthManager(rest_client_factory, self.cache)
        # Handle remote connections
        self.remote_manager = RemoteManager(self.cache, auth_manager, self.hook_manager)

        # Adjust global tool variables
        set_global_instances(self.requester, self.config)

        self.runner = ConanRunner(self.config.print_commands_to_output,
                                  self.config.generate_run_log_file,
                                  self.config.log_run_to_output)

        self.proxy = ConanProxy(self)
        self.range_resolver = RangeResolver(self)

        self.pyreq_loader = PyRequireLoader(self.proxy, self.range_resolver)
        self.loader = ConanFileLoader(self.runner, self.pyreq_loader, self.requester)
        self.binaries_analyzer = GraphBinariesAnalyzer(self)
        self.graph_manager = GraphManager(self)

        # Remotes
        self.selected_remotes = []
        self.enabled_remotes = []
        self.all_remotes = []
        self.update = False
        self.check_updates = False

    @property
    def selected_remote(self):
        # FIXME: To ease the migration to N selected remotes
        if len(self.selected_remotes) == 0:
            return None
        if len(self.selected_remotes) == 1:
            return self.selected_remotes[0]
        else:
            assert False, "It makes no sense to obtain the selected remote when there are several " \
                          "selected remotes"

    def load_remotes(self, remotes=None, update=False, check_updates=False):
        self.all_remotes = self.cache.remotes_registry.list()
        self.enabled_remotes = [r for r in self.all_remotes if not r.disabled]
        self.update = update
        self.check_updates = check_updates
        self.selected_remotes = []
        if remotes:
            for r in remotes:
                if r.name is not None:  # FIXME: Remove this when we pass always remote objects
                    tmp = self.cache.remotes_registry.read(r.name)
                    if tmp.disabled:
                        raise ConanException("Remote '{}' is disabled".format(tmp.name))
                    self.selected_remotes.append(tmp)
