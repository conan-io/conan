from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference
from conans.model.version_range import VersionRange
from conans.search.search import search_recipes


class RangeResolver:

    def __init__(self, conan_app):
        self._cache = conan_app.cache
        self._remote_manager = conan_app.remote_manager
        self._cached_cache = {}  # Cache caching of search result, so invariant wrt installations
        self._cached_remote_found = {}  # dict {ref (pkg/*): {remote_name: results (pkg/1, pkg/2)}}
        self.resolved_ranges = {}

    def resolve(self, require, base_conanref, remotes, update):
        version_range = require.version_range
        if version_range is None:
            return
        assert isinstance(version_range, VersionRange)

        # Check if this ref with version range was already solved
        previous_ref = self.resolved_ranges.get(require.ref)
        if previous_ref is not None:
            require.ref = previous_ref
            return

        ref = require.ref
        # The search pattern must be a string
        search_ref = str(RecipeReference(ref.name, "*", ref.user, ref.channel))

        resolved_ref = self._resolve_local(search_ref, version_range)
        if resolved_ref is None or update:
            remote_resolved_ref = self._resolve_remote(search_ref, version_range, remotes, update)
            if resolved_ref is None or (remote_resolved_ref is not None and
                                        resolved_ref.version < remote_resolved_ref.version):
                resolved_ref = remote_resolved_ref

        if resolved_ref is None:
            raise ConanException("Version range '%s' from requirement '%s' required by '%s' "
                                 "could not be resolved" % (version_range, require, base_conanref))

        # To fix Cache behavior, we remove the revision information
        resolved_ref.revision = None  # FIXME: Wasting information already obtained from server?
        self.resolved_ranges[require.ref] = resolved_ref
        require.ref = resolved_ref

    def _resolve_local(self, search_ref, version_range):
        local_found = self._cached_cache.get(search_ref)
        if local_found is None:
            # This local_found is weird, it contains multiple revisions, not just latest
            local_found = search_recipes(self._cache, search_ref)
            self._cached_cache[search_ref] = local_found
        if local_found:
            return self._resolve_version(version_range, local_found)

    def _search_remote_recipes(self, remote, search_ref):
        pattern_cached = self._cached_remote_found.setdefault(search_ref, {})
        results = pattern_cached.get(remote.name)
        if results is None:
            results = self._remote_manager.search_recipes(remote, search_ref)
            pattern_cached.update({remote.name: results})
        return results

    def _resolve_remote(self, search_ref, version_range, remotes, update):
        update_candidates = []
        for remote in remotes:
            remote_results = self._search_remote_recipes(remote, search_ref)
            resolved_version = self._resolve_version(version_range, remote_results)
            if resolved_version:
                if not update:
                    return resolved_version  # Return first valid occurence in first remote
                else:
                    update_candidates.append(resolved_version)
        if len(update_candidates) > 0:  # pick latest from already resolved candidates
            resolved_version = self._resolve_version(version_range, update_candidates)
            return resolved_version

    @staticmethod
    def _resolve_version(version_range, refs_found):
        for ref in reversed(sorted(refs_found)):
            if ref.version in version_range:
                return ref
