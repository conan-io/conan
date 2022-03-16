import sys

from conans import __version__ as client_version
from conans.cli.api.subapi.config import ConfigAPI
from conans.cli.api.subapi.download import DownloadAPI
from conans.cli.api.subapi.export import ExportAPI
from conans.cli.api.subapi.install import InstallAPI
from conans.cli.api.subapi.graph import GraphAPI
from conans.cli.api.subapi.new import NewAPI
from conans.cli.api.subapi.profiles import ProfilesAPI
from conans.cli.api.subapi.list import ListAPI
from conans.cli.api.subapi.remotes import RemotesAPI
from conans.cli.api.subapi.remove import RemoveAPI
from conans.cli.api.subapi.search import SearchAPI
from conans.cli.api.subapi.upload import UploadAPI
from conans.client.conf.required_version import check_required_conan_version
from conans.client.migrations import ClientMigrator
from conans.client.userio import init_colorama
from conans.errors import ConanException
from conans.model.version import Version
from conans.paths import get_conan_user_home


class ConanAPIV2(object):
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
        check_required_conan_version(self.cache_folder)

        # Remotes management
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


ConanAPI = ConanAPIV2
