import sys

from conan.api.subapi.cache import CacheAPI
from conan.api.subapi.command import CommandAPI
from conan.api.subapi.local import LocalAPI
from conan.api.subapi.lockfile import LockfileAPI
from conans import __version__ as client_version
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
from conans.client.conf.required_version import check_required_conan_version
from conans.client.migrations import ClientMigrator
from conans.client.userio import init_colorama
from conans.errors import ConanException
from conans.model.version import Version
from conan.internal.paths import get_conan_user_home


class ConanAPI(object):
    def __init__(self, cache_folder=None):

        version = sys.version_info
        if version.major == 2 or version.minor < 6:
            raise ConanException("Conan needs Python >= 3.6")

        init_colorama(sys.stderr)
        self.cache_folder = cache_folder or get_conan_user_home()
        self.home_folder = self.cache_folder  # Lets call it home, deprecate "cache"

        # Migration system
        migrator = ClientMigrator(self.cache_folder, Version(client_version))
        migrator.migrate()

        self.command = CommandAPI(self)
        self.remotes = RemotesAPI(self)
        # Search recipes by wildcard and packages filtering by configuracion
        self.search = SearchAPI(self)
        # Get latest refs and list refs of recipes and packages
        self.list = ListAPI(self)
        self.profiles = ProfilesAPI(self)
        self.install = InstallAPI(self)
        self.graph = GraphAPI(self)
        self.export = ExportAPI(self)
        self.remove = RemoveAPI(self)
        self.config = ConfigAPI(self)
        self.new = NewAPI(self)
        self.upload = UploadAPI(self)
        self.download = DownloadAPI(self)
        self.cache = CacheAPI(self)
        self.lockfile = LockfileAPI(self)
        self.local = LocalAPI(self)

        check_required_conan_version(self.config.global_conf)
