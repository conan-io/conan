import fnmatch
from collections import OrderedDict, namedtuple

from conans.search.search import (search_recipes)


class Search(object):
    def __init__(self, cache, remote_manager, remotes):
        self._cache = cache
        self._remote_manager = remote_manager
        self._remotes = remotes

    def search_recipes(self, query, remote_pattern=None):
        ignorecase = True

        references = OrderedDict()
        if remote_pattern is None:
            references[None] = search_recipes(self._cache, query, ignorecase)
            return references

        for remote in self._remotes.values():
            if fnmatch.fnmatch(remote.name, remote_pattern):
                refs = self._remote_manager.search_recipes(remote, query, ignorecase)
                if refs:
                    references[remote.name] = sorted(refs)
        return references
