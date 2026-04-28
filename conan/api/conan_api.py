import os
import sys

from conan.api.output import init_colorama
from conan.api.subapi.audit import AuditAPI
from conan.api.subapi.cache import CacheAPI
from conan.api.subapi.command import CommandAPI
from conan.api.subapi.local import LocalAPI
from conan.api.subapi.lockfile import LockfileAPI
from conan.api.subapi.report import ReportAPI
from conan.api.subapi.workspace import WorkspaceAPI
from conan.api.subapi.config import ConfigAPI
from conan.api.subapi.download import DownloadAPI
from conan.api.subapi.export import ExportAPI
from conan.api.subapi.install import InstallAPI
from conan.api.subapi.graph import GraphAPI
from conan.api.subapi.new import NewAPI
from conan.api.subapi.profiles import ProfilesAPI
from conan.api.subapi.list import ListAPI
from conan.api.subapi.remotes import RemotesAPI
from conan.api.subapi.remove import RemoveAPI
from conan.api.subapi.upload import UploadAPI
from conan.errors import ConanException
from conan.internal.api.remotes.localdb import LocalDB
from conan.internal.cache.cache import PkgCache
from conan.internal.cache.home_paths import HomePaths
from conan.internal.conan_app import ConanFileHelpers, CmdWrapper
from conan.internal.graph.proxy import ConanProxy
from conan.internal.graph.python_requires import PyRequireLoader
from conan.internal.graph.range_resolver import RangeResolver
from conan.internal.hook_manager import HookManager
from conan.internal.loader import ConanFileLoader, load_python_file
from conan.internal.model.conf import load_global_conf, ConfDefinition, CORE_CONF_PATTERN
from conan.internal.model.settings import load_settings_yml
from conan.internal.paths import get_conan_user_home
from conan.internal.api.local.editable import EditablePackages
from conan.internal.api.migrations import ClientMigrator
from conan.internal.model.version_range import validate_conan_version
from conan.internal.rest.auth_manager import ConanApiAuthManager
from conan.internal.rest.conan_requester import ConanRequester
from conan.internal.rest.remote_manager import RemoteManager


class ConanAPI:
    """
    This is the main object to interact with the Conan API. It provides all the subapis to work with
    recipes, packages, remotes, etc., which are exposed as attributes of this class, and should
    not be created directly.
    """
    def __init__(self, cache_folder=None):
        """
        :param cache_folder: Conan cache/home folder. It will have less priority than the
                             ``"home_folder"`` defined in a Workspace.
        """

        version = sys.version_info
        if version.major == 2 or version.minor < 7:
            raise ConanException("Conan needs Python >= 3.7")
        if cache_folder is not None and not os.path.isabs(cache_folder):
            raise ConanException("cache_folder has to be an absolute path")

        init_colorama(sys.stderr)
        # Deprecated, but still used internally, prefer home_folder
        self.cache_folder = cache_folder or get_conan_user_home()
        self._home_folder = self.cache_folder
        self._api_helpers = self._ApiHelpers(self)
        self.migrate()

        #: Used to interact with the local Conan configuration
        self.config: ConfigAPI = ConfigAPI(self, self._api_helpers)
        #: Used to interact with remotes
        self.remotes: RemotesAPI = RemotesAPI(self, self._api_helpers)
        #: Used to call other commands
        self.command: CommandAPI = CommandAPI(self)
        #: Used to get latest refs and list refs of recipes and packages
        self.list: ListAPI = ListAPI(self, self._api_helpers)
        #: Used to process and load Conan profiles
        self.profiles: ProfilesAPI = ProfilesAPI(self, self._api_helpers)
        #: Used to install binaries, sources, deploy packages and more
        self.install: InstallAPI = InstallAPI(self, self._api_helpers)
        self.graph = GraphAPI(self, self._api_helpers)
        #: Used to export recipes and pre-compiled package binaries to the Conan cache
        self.export: ExportAPI = ExportAPI(self, self._api_helpers)
        self.remove = RemoveAPI(self, self._api_helpers)
        self.new = NewAPI(self)
        #: Used to upload recipes and packages to remotes
        self.upload: UploadAPI = UploadAPI(self, self._api_helpers)
        #: Used to download recipes and packages from remotes
        self.download: DownloadAPI = DownloadAPI(self, self._api_helpers)
        #: Used to interact wit the packages storage cache
        self.cache: CacheAPI = CacheAPI(self, self._api_helpers)
        #: Used to read and manage lockfile files
        self.lockfile: LockfileAPI = LockfileAPI(self)
        #: Local flow helpers for developer "source", "build", "editable" commands
        self.local: LocalAPI = LocalAPI(self, self._api_helpers)
        #: Used to check vulnerabilities of dependencies
        self.audit: AuditAPI = AuditAPI(self)
        #: Used to manage workspaces
        self.workspace: WorkspaceAPI = WorkspaceAPI(self)
        self.report: ReportAPI = ReportAPI(self, self._api_helpers)

    @property
    def home_folder(self) -> str:
        """ Where the Conan user home is located. Read only.
        Can be modified by the ``CONAN_HOME`` environment variable or by the
        ``.conanrc`` file in the current directory or any parent directory
        when Conan is called.
        """
        return self._home_folder

    def reinit(self):
        """
        Reinitialize the Conan API. This is useful when the configuration changes.
        """
        self._api_helpers.reinit()

    def migrate(self):
        # Migration system
        # TODO: A prettier refactoring of migrators would be nice
        from conan import conan_version
        migrator = ClientMigrator(self._home_folder, conan_version)
        migrator.migrate()

    class _ApiHelpers:
        # This is an internal implementation detail of Conan, DO NOT USE
        def __init__(self, conan_api):
            self._conan_api = conan_api
            self._cli_core_confs = None
            self._init_global_conf()
            # TODO: Make uniform lazy vs non lazy collaborators
            self.hook_manager = HookManager(HomePaths(self._conan_api.home_folder).hooks_path)
            self._editable_packages = EditablePackages(self._conan_api.home_folder)
            # Wraps an http_requester to inject proxies, certs, etc
            self._requester = ConanRequester(self.global_conf, self._conan_api.home_folder)
            self.cache = PkgCache(self._conan_api.home_folder, self.global_conf)
            self._settings_yml = None
            self._remote_manager = None

        def set_core_confs(self, core_confs):
            confs = ConfDefinition()
            for c in core_confs:
                if not CORE_CONF_PATTERN.match(c):
                    raise ConanException(f"Only core. values are allowed in --core-conf. Got {c}")
            confs.loads("\n".join(core_confs))
            confs.validate()
            self._cli_core_confs = confs
            # Last but not least, apply the new configuration
            # This will in turn call ApiHelpers.reinit() as the very first thing
            self._conan_api.reinit()

        def _init_global_conf(self):
            self.global_conf = load_global_conf(self._conan_api.home_folder)
            if self._cli_core_confs:
                self.global_conf.update_conf_definition(self._cli_core_confs)
            required_range_new = self.global_conf.get("core:required_conan_version")
            if required_range_new:
                validate_conan_version(required_range_new)
            self.global_conf.validate()

        def reinit(self):
            self._init_global_conf()
            self.hook_manager.reinit()
            self._requester = ConanRequester(self.global_conf, self._conan_api.home_folder)
            self._settings_yml = None
            self.cache = PkgCache(self._conan_api.home_folder, self.global_conf)
            self._remote_manager = None
            self._editable_packages = EditablePackages(self._conan_api.home_folder)

        @property
        def settings_yml(self):
            if self._settings_yml is None:
                self._settings_yml = load_settings_yml(self._conan_api.home_folder)
            return self._settings_yml

        @property
        def remote_manager(self):
            if self._remote_manager is None:
                home_folder = self._conan_api.home_folder
                localdb = LocalDB(home_folder)
                requester = self._conan_api._api_helpers.requester  # noqa
                auth_manager = ConanApiAuthManager(requester, self._conan_api.home_folder, localdb,
                                                   self.global_conf)
                self._remote_manager = RemoteManager(self.cache, auth_manager, home_folder)
            return self._remote_manager

        @property
        def requester(self):
            return self._requester

        @property
        def editable_packages(self):
            # These are just the global editables, not including workspace ones
            return self._editable_packages

        @property
        def loader(self):
            _, _, load, _ = self.get_loader()
            return load

        def _flags_plugin(self):
            plugin_path = os.path.join(self._conan_api.home_folder, "extensions", "plugins",
                                       "compiler_flags.py")
            if os.path.isfile(plugin_path):
                mod, _ = load_python_file(plugin_path)
                return mod.flags_map
            return None

        def get_loader(self):
            ws_editables = self._conan_api.workspace.packages()
            editable_packages = self._editable_packages.update_copy(ws_editables)

            legacy_update = self.global_conf.get("core:update_policy", choices=["legacy"])
            # This proxy is caching information
            proxy = ConanProxy(self.cache, self.remote_manager, editable_packages,
                               legacy_update=legacy_update)
            # This is caching too
            range_resolver = RangeResolver(self.cache, self.remote_manager, self.global_conf,
                                           editable_packages)

            cmd_wrap = CmdWrapper(HomePaths(self._conan_api.home_folder).wrapper_path)
            conanfile_helpers = ConanFileHelpers(self._requester, cmd_wrap, self.global_conf,
                                                 self.cache, self._conan_api.home_folder,
                                                 self._conan_api, flags_map=self._flags_plugin())
            pyreq_loader = PyRequireLoader(proxy, range_resolver, self.global_conf)
            # This is caching too!
            loader = ConanFileLoader(pyreq_loader, conanfile_helpers)
            return proxy, range_resolver, loader, None
