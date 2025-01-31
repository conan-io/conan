import sys

from conan.api.output import init_colorama
from conan.api.subapi.cache import CacheAPI
from conan.api.subapi.command import CommandAPI
from conan.api.subapi.local import LocalAPI
from conan.api.subapi.lockfile import LockfileAPI
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
from conan.api.subapi.search import SearchAPI
from conan.api.subapi.upload import UploadAPI
from conan.errors import ConanException
from conan.internal.paths import get_conan_user_home
from conans.client.migrations import ClientMigrator
from conan.internal.model.version_range import validate_conan_version


class ConanAPI:
    """
    This is the main object to interact with the Conan API. It provides all the subapis to work with
    recipes, packages, remotes, etc., which are exposed as attributes of this class, and should
    not be created directly.
    """
    def __init__(self, cache_folder=None):

        version = sys.version_info
        if version.major == 2 or version.minor < 6:
            raise ConanException("Conan needs Python >= 3.6")

        init_colorama(sys.stderr)
        self.workspace = WorkspaceAPI(self)
        self.cache_folder = self.workspace.home_folder() or cache_folder or get_conan_user_home()
        self.home_folder = self.cache_folder  # Lets call it home, deprecate "cache"
        self.migrate()

        # This API is depended upon by the subsequent ones, it should be initialized first
        self.config = ConfigAPI(self)

        self.remotes = RemotesAPI(self)
        self.command = CommandAPI(self)
        # Search recipes by wildcard and packages filtering by configuration
        self.search = SearchAPI(self)
        # Get latest refs and list refs of recipes and packages
        self.list = ListAPI(self)
        self.profiles = ProfilesAPI(self)
        self.install = InstallAPI(self)
        self.graph = GraphAPI(self)
        self.export = ExportAPI(self)
        self.remove = RemoveAPI(self)
        self.new = NewAPI(self)
        self.upload = UploadAPI(self)
        self.download = DownloadAPI(self)
        self.cache = CacheAPI(self)
        self.lockfile = LockfileAPI(self)
        self.local = LocalAPI(self)

        _check_conan_version(self)

    def reinit(self):
        """
        Reinitialize the Conan API. This is useful when the configuration changes.
        """
        self.config.reinit()
        self.remotes.reinit()
        self.local.reinit()

        _check_conan_version(self)

    def migrate(self):
        # Migration system
        # TODO: A prettier refactoring of migrators would be nice
        from conan import conan_version
        migrator = ClientMigrator(self.cache_folder, conan_version)
        migrator.migrate()


def _check_conan_version(conan_api):
    required_range_new = conan_api.config.global_conf.get("core:required_conan_version")
    if required_range_new:
        validate_conan_version(required_range_new)
