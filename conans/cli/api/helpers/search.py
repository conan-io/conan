from collections import OrderedDict

from conans.cli.conan_app import ConanApp
from conans.search.search import search_recipes


class Search(object):
    def __init__(self, app: ConanApp):
        self._app = app
        self._cache = app.cache
        self._remote_manager = app.remote_manager

    def search_local_recipes(self, pattern):
        return search_recipes(self._cache, pattern)

    def search_remote_recipes(self, pattern, remote_name):
        references = OrderedDict()
        remote = self._app.get_active_remote_by_name(remote_name)
        refs = self._remote_manager.search_recipes(remote, pattern)
        references[remote.name] = sorted(refs)
        return references
