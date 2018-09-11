from conans.search.search import filter_outdated, search_recipes,\
    search_packages
from collections import OrderedDict, namedtuple
from conans.errors import NotFoundException


class Search(object):
    def __init__(self, client_cache, remote_manager, remote_registry):
        self._client_cache = client_cache
        self._remote_manager = remote_manager
        self._registry = remote_registry

    def search_recipes(self, pattern, remote_name=None, case_sensitive=False):
        ignorecase = not case_sensitive

        references = OrderedDict()
        if not remote_name:
            references[None] = search_recipes(self._client_cache, pattern, ignorecase)
            return references

        if remote_name == 'all':
            remotes = self._registry.remotes
            # We have to check if there is a remote called "all"
            # Deprecate: 2.0 can remove this check
            if 'all' not in (r.name for r in remotes):
                for remote in remotes:
                    refs = self._remote_manager.search_recipes(remote, pattern, ignorecase)
                    if refs:
                        references[remote.name] = refs
                return references
        # single remote
        remote = self._registry.remote(remote_name)
        refs = self._remote_manager.search_recipes(remote, pattern, ignorecase)
        references[remote.name] = refs
        return references

    remote_ref = namedtuple('remote_ref', 'ordered_packages recipe_hash')

    def search_packages(self, reference=None, remote_name=None, query=None, outdated=False):
        """ Return the single information saved in conan.vars about all the packages
            or the packages which match with a pattern

            Attributes:
                pattern = string to match packages
                remote_name = search on another origin to get packages info
                packages_pattern = String query with binary
                                   packages properties: "arch=x86 AND os=Windows"
        """
        if not remote_name:
            return self._search_packages_in_local(reference, query, outdated)

        if remote_name == 'all':
            return self._search_packages_in_all(reference, query, outdated)

        return self._search_packages_in(remote_name, reference, query, outdated)

    def _search_packages_in_local(self, reference=None, query=None, outdated=False):
        packages_props = search_packages(self._client_cache, reference, query)
        ordered_packages = OrderedDict(sorted(packages_props.items()))
        try:
            recipe_hash = self._client_cache.load_manifest(reference).summary_hash
        except IOError:  # It could not exist in local
            recipe_hash = None

        if outdated and recipe_hash:
            ordered_packages = filter_outdated(ordered_packages, recipe_hash)

        references = OrderedDict()
        references[None] = self.remote_ref(ordered_packages, recipe_hash)
        return references

    def _search_packages_in_all(self, reference=None, query=None, outdated=False):
        references = OrderedDict()
        remotes = self._registry.remotes
        # We have to check if there is a remote called "all"
        # Deprecate: 2.0 can remove this check
        if 'all' not in (r.name for r in remotes):
            for remote in remotes:
                try:
                    packages_props = self._remote_manager.search_packages(remote, reference, query)
                    if packages_props:
                        ordered_packages = OrderedDict(sorted(packages_props.items()))
                        manifest = self._remote_manager.get_conan_manifest(reference, remote)
                        recipe_hash = manifest.summary_hash

                        if outdated and recipe_hash:
                            ordered_packages = filter_outdated(ordered_packages, recipe_hash)

                        references[remote.name] = self.remote_ref(ordered_packages, recipe_hash)
                except NotFoundException:
                    continue
            return references

        return self._search_packages_in(self, 'all', reference, query, outdated)

    def _search_packages_in(self, remote_name, reference=None, query=None, outdated=False):
        remote = self._registry.remote(remote_name)
        packages_props = self._remote_manager.search_packages(remote, reference, query)
        ordered_packages = OrderedDict(sorted(packages_props.items()))
        manifest = self._remote_manager.get_conan_manifest(reference, remote)
        recipe_hash = manifest.summary_hash

        if outdated and recipe_hash:
            ordered_packages = filter_outdated(ordered_packages, recipe_hash)

        references = OrderedDict()
        references[remote.name] = self.remote_ref(ordered_packages, recipe_hash)
        return references
