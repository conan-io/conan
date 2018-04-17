from conans.search.search import DiskSearchManager, filter_outdated
from collections import OrderedDict


class Search(object):
    def __init__(self, client_cache, remote_manager, remote_registry):
        self._client_cache = client_cache
        self._remote_manager = remote_manager
        self._registry = remote_registry

    def search_recipes(self, pattern, remote=None, case_sensitive=False):
        ignorecase = not case_sensitive
        if not remote:
            return DiskSearchManager(self._client_cache).search_recipes(pattern, ignorecase)

        if remote == 'all':
            remotes = self._registry.remotes
            # We have to check if there is a remote called "all"
            # Deprecate: 2.0 can remove this check
            if 'all' not in (r.name for r in remotes):
                references = {}
                for remote in remotes:
                    result = self._remote_manager.search_recipes(remote, pattern, ignorecase)
                    if result:
                        references[remote.name] = result
                return references
        # single remote
        remote = self._registry.remote(remote)
        return self._remote_manager.search_recipes(remote, pattern, ignorecase)

    def search_packages(self, reference=None, remote_name=None, query=None, outdated=False):
        """ Return the single information saved in conan.vars about all the packages
            or the packages which match with a pattern

            Attributes:
                pattern = string to match packages
                remote = search on another origin to get packages info
                packages_pattern = String query with binary
                                   packages properties: "arch=x86 AND os=Windows"
        """
        if remote_name:
            remote = self._registry.remote(remote_name)
            packages_props = self._remote_manager.search_packages(remote, reference, query)
            ordered_packages = OrderedDict(sorted(packages_props.items()))
            manifest = self._remote_manager.get_conan_manifest(reference, remote)
            recipe_hash = manifest.summary_hash
        else:
            searcher = DiskSearchManager(self._client_cache)
            packages_props = searcher.search_packages(reference, query)
            ordered_packages = OrderedDict(sorted(packages_props.items()))
            try:
                recipe_hash = self._client_cache.load_manifest(reference).summary_hash
            except IOError:  # It could not exist in local
                recipe_hash = None
        if outdated and recipe_hash:
            ordered_packages = filter_outdated(ordered_packages, recipe_hash)
        return ordered_packages, reference, recipe_hash, query
