import fnmatch
from collections import OrderedDict, namedtuple

from conans.errors import NoRemoteAvailable, ConanException, NotFoundException
from conans.search.search import (search_recipes, search_packages, filter_outdated,
                                  filter_by_revision)


class Search(object):
    def __init__(self, cache, remote_manager, remotes):
        self._cache = cache
        self._remote_manager = remote_manager
        self._remotes = remotes

    def search_recipes(self, query, remote_patterns=[]):
        ignorecase = True

        references = OrderedDict()
        if len(remote_patterns) == 0:
            references[None] = search_recipes(self._cache, query, ignorecase)
            return references
        else:
            matches = False
            for remote in self._remotes.values():
                for remote_pattern in remote_patterns:
                    if fnmatch.fnmatch(remote.name, remote_pattern):
                        matches = True
                        refs = self._remote_manager.search_recipes(remote, query, ignorecase)
                        references[remote.name] = sorted(refs)
            if not matches:
                raise NoRemoteAvailable("No remotes defined matching patterns {}".format(', '.join(r for r in remote_patterns)))
        return references

    remote_ref = namedtuple('remote_ref', 'ordered_packages recipe_hash')

    def search_packages(self, ref=None, remote_patterns=None, query=None, outdated=False):
        """ Return the single information saved in conan.vars about all the packages
            or the packages which match with a pattern

            Attributes:
                pattern = string to match packages
                remote_name = search on another origin to get packages info
                packages_pattern = String query with binary
                                   packages properties: "arch=x86 AND os=Windows"
        """
        packages = OrderedDict()
        if len(remote_patterns) == 0:
            packages[None] = self._search_packages_in_local(ref, query, outdated)
        else:
            matches = False
            for remote in self._remotes.values():
                for remote_pattern in remote_patterns:
                    if fnmatch.fnmatch(remote.name, remote_pattern):
                        matches = True
                        try:
                            packages_in_remote = self._search_packages_in(remote, ref, query, outdated)
                            packages[remote.name] = packages_in_remote
                        except NotFoundException:
                            pass
            if not matches:
                raise NoRemoteAvailable("No remotes defined matching patterns {}".format(', '.join(r for r in remote_patterns)))
        return packages

    def _search_packages_in_local(self, ref=None, query=None, outdated=False):
        package_layout = self._cache.package_layout(ref, short_paths=None)
        packages_props = search_packages(package_layout, query)
        ordered_packages = OrderedDict(sorted(packages_props.items()))

        try:
            recipe_hash = package_layout.recipe_manifest().summary_hash
        except IOError:  # It could not exist in local
            recipe_hash = None

        if outdated:
            ordered_packages = filter_outdated(ordered_packages, recipe_hash)
        elif self._cache.config.revisions_enabled:
            # With revisions, by default filter the packages not belonging to the recipe
            # unless outdated is specified.
            metadata = package_layout.load_metadata()
            ordered_packages = filter_by_revision(metadata, ordered_packages)

        return self.remote_ref(ordered_packages, recipe_hash)

    def _search_packages_in(self, remote, ref=None, query=None, outdated=False):
        packages_props = self._remote_manager.search_packages(remote, ref, query)
        ordered_packages = OrderedDict(sorted(packages_props.items()))
        manifest, ref = self._remote_manager.get_recipe_manifest(ref, remote)

        recipe_hash = manifest.summary_hash

        if outdated and recipe_hash:
            ordered_packages = filter_outdated(ordered_packages, recipe_hash)

        return self.remote_ref(ordered_packages, recipe_hash)
