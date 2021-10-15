from collections import OrderedDict

from conans.search.search import search_recipes


class Search(object):
    def __init__(self, cache, remote_manager, remotes):
        self._cache = cache
        self._remote_manager = remote_manager
        self._remotes = remotes

    def search_local_recipes(self, pattern):
        return search_recipes(self._cache, pattern)

    def search_remote_recipes(self, pattern, remote_name):
        references = OrderedDict()
        remote = self._remotes[remote_name]
        refs = self._remote_manager.search_recipes(remote, pattern)
        references[remote.name] = sorted(refs)
        return references
