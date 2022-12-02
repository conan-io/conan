from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference
from conans.model.version_range import VersionRange
from conans.search.search import search_recipes


class RangeResolver(object):

    def __init__(self, conan_app):
        self._cache = conan_app.cache
        self._remote_manager = conan_app.remote_manager
        self._cached_cache = {}  # Cache caching of search result, so invariant wrt installations
        self._cached_remote_found = {}  # dict {ref (pkg/*): {remote_name: results (pkg/1, pkg/2)}}
        self.resolved_ranges = {}

    def _search_remote_recipes(self, remote, search_ref):
        pattern = str(search_ref)
        pattern_cached = self._cached_remote_found.setdefault(pattern, {})
        results = pattern_cached.get(remote.name)
        if results is None:
            results = self._remote_manager.search_recipes(remote, pattern)
            pattern_cached.update({remote.name: results})
        return results

    def resolve(self, require, base_conanref, remotes, update):
        self._update = update
        version_range = require.version_range
        if version_range is None:
            return require.ref

        # Check if this ref with version range was already solved
        prev = self.resolved_ranges.get(require.ref)
        if prev is not None:
            require.ref = prev
            return prev

        ref = require.ref
        # The search pattern must be a string
        search_ref = RecipeReference(ref.name, "*", ref.user, ref.channel)

        resolved_ref = self._resolve_local(search_ref, version_range)
        if resolved_ref is None or self._update:
            remote_resolved_ref = self._resolve_remote(search_ref, version_range, remotes)
            if resolved_ref is None or (remote_resolved_ref is not None and
                                        resolved_ref.version < remote_resolved_ref.version):
                resolved_ref = remote_resolved_ref

        if resolved_ref is None:
            raise ConanException("Version range '%s' from requirement '%s' required by '%s' "
                                 "could not be resolved" % (version_range, require, base_conanref))

        self.resolved_ranges[require.ref] = resolved_ref
        require.ref = resolved_ref
        return resolved_ref

    def _resolve_local(self, search_ref, version_range):
        local_found = self._cached_cache.get(search_ref)
        if local_found is None:
            # This local_found is weird, it contains multiple revisions, not just latest
            local_found = search_recipes(self._cache, search_ref)
            local_found = [ref for ref in local_found
                           if ref.user == search_ref.user and ref.channel == search_ref.channel]
            self._cached_cache[search_ref] = local_found
        if local_found:
            return self._resolve_version(version_range, local_found)

    def _search_and_resolve_remotes(self, search_ref, version_range, remotes):
        results = []
        for remote in remotes:
            remote_results = self._search_remote_recipes(remote, search_ref)
            remote_results = [ref for ref in remote_results
                              if ref.user == search_ref.user
                              and ref.channel == search_ref.channel]
            resolved_version = self._resolve_version(version_range, remote_results)
            if resolved_version and not self._update:
                return resolved_version
            elif resolved_version:
                results.append({"remote": remote.name,
                                "version": resolved_version})
        if len(results) > 0:
            resolved_version = self._resolve_version(version_range,
                                                     [result.get("version") for result in results])
            for result in results:
                if result.get("version") == resolved_version:
                    return result.get("version")
        else:
            return None

    def _resolve_remote(self, search_ref, version_range, remotes):
        # Searching for just the name is much faster in remotes like Artifactory
        resolved_ref  = self._search_and_resolve_remotes(search_ref, version_range, remotes)
        # We don't want here to resolve the revision that should be done in the proxy
        # as any other regular flow
        # FIXME: refactor all this and update for 2.0
        if not resolved_ref:
            return None
        resolved_ref.revision = None  # FIXME: Wasting information already obtained from server?
        return resolved_ref

    @staticmethod
    def _resolve_version(version_range, refs_found):
        assert isinstance(version_range, VersionRange)
        for ref in reversed(sorted(r for r in refs_found if r is not None)):
            if ref.version in version_range:
                return ref
