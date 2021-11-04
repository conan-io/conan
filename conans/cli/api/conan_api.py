import sys

from conans import __version__ as client_version
from conans.cli.api.subapi.list import ListAPI
from conans.cli.api.subapi.remotes import RemotesAPI
from conans.cli.api.subapi.search import SearchAPI
from conans.cli.output import ConanOutput
from conans.client.conf.required_version import check_required_conan_version
from conans.client.migrations import ClientMigrator
from conans.errors import ConanException
from conans.model.version import Version
from conans.paths import get_conan_user_home


class ConanAPIV2(object):
    def __init__(self, cache_folder=None):

        version = sys.version_info
        if version.major == 2 or version.minor < 6:
            raise ConanException("Conan needs Python >= 3.6")

        self.out = ConanOutput()
        self.cache_folder = cache_folder or get_conan_user_home()

        # Migration system
        migrator = ClientMigrator(self.cache_folder, Version(client_version))
        migrator.migrate()
        check_required_conan_version(self.cache_folder)

        # Remotes management
        self.remotes = RemotesAPI(self)

        # Search
        self.search = SearchAPI(self)

        # List management
        self.list = ListAPI(self)


ConanAPI = ConanAPIV2
