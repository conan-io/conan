import re

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.search.search import search_recipes

re_param = re.compile(r"^(?P<function>include_prerelease|loose)\s*=\s*(?P<value>True|False)$")
re_version = re.compile(r"^((?!(include_prerelease|loose))[a-zA-Z0-9_+.\-~<>=|*^\s])*$")


def _parse_versionexpr(versionexpr, result):
    expression = [it.strip() for it in versionexpr.split(",")]
    if len(expression) > 4:
        raise ConanException("Invalid expression for version_range '{}'".format(versionexpr))

    include_prerelease = False
    loose = True
    version_range = []

    for i, expr in enumerate(expression):
        match_param = re_param.match(expr)
        match_version = re_version.match(expr)

        if match_param == match_version:
            raise ConanException("Invalid version range '{}', failed in "
                                 "chunk '{}'".format(versionexpr, expr))

        if match_version and i not in [0, 1]:
            raise ConanException("Invalid version range '{}'".format(versionexpr))

        if match_param and i not in [1, 2, 3]:
            raise ConanException("Invalid version range '{}'".format(versionexpr))

        if match_version:
            version_range.append(expr)

        if match_param:
            if match_param.group('function') == 'loose':
                loose = match_param.group('value') == "True"
            elif match_param.group('function') == 'include_prerelease':
                include_prerelease = match_param.group('value') == "True"
            else:
                raise ConanException("Unexpected version range "
                                     "parameter '{}'".format(match_param.group(1)))

    if len(version_range) > 1:
        result.append("WARN: Commas as separator in version '%s' range are deprecated "
                      "and will be removed in Conan 2.0" % str(versionexpr))

    version_range = " ".join(map(str, version_range))
    return version_range, loose, include_prerelease


def satisfying(list_versions, versionexpr, result):
    """ returns the maximum version that satisfies the expression
    if some version cannot be converted to loose SemVer, it is discarded with a msg
    This provides some workaround for failing comparisons like "2.1" not matching "<=2.1"
    """
    from semver import SemVer, Range, max_satisfying
    version_range, loose, include_prerelease = _parse_versionexpr(versionexpr, result)

    # Check version range expression
    try:
        act_range = Range(version_range, loose)
    except ValueError:
        raise ConanException("version range expression '%s' is not valid" % version_range)

    # Validate all versions
    candidates = {}
    for v in list_versions:
        try:
            ver = SemVer(v, loose=loose)
            candidates[ver] = v
        except (ValueError, AttributeError):
            result.append("WARN: Version '%s' is not semver, cannot be compared with a range"
                          % str(v))

    # Search best matching version in range
    result = max_satisfying(candidates, act_range, loose=loose,
                            include_prerelease=include_prerelease)
    return candidates.get(result)


def range_satisfies(version_range, version):
    from semver import satisfies
    rang, loose, include_prerelease = _parse_versionexpr(version_range, [])
    return satisfies(version, rang, loose=loose, include_prerelease=include_prerelease)


class RangeResolver(object):

    def __init__(self, conan_app):
        self._cache = conan_app.cache
        self._remote_manager = conan_app.remote_manager
        self._conan_app = conan_app
        self._cached_cache = {}  # Cache caching of search result, so invariant wrt installations
        self._cached_remote_found = {}  # dict {ref (pkg/*): {remote_name: results (pkg/1, pkg/2)}}
        self._result = []

    def _search_remote_recipes(self, remote, search_ref):
        pattern = str(search_ref)
        pattern_cached = self._cached_remote_found.setdefault(pattern, {})
        results = pattern_cached.get(remote.name)
        if results is None:
            results = self._remote_manager.search_recipes(remote, pattern, ignorecase=False)
            pattern_cached.update({remote.name: results})
        return results

    @property
    def output(self):
        return self._result

    def clear_output(self):
        self._result = []

    def resolve(self, require, base_conanref):
        version_range = require.version_range
        if version_range is None:
            return require.ref

        ref = require.ref
        # The search pattern must be a string
        search_ref = ConanFileReference(ref.name, "*", ref.user, ref.channel)

        remote_name = None
        remote_resolved_ref = None
        resolved_ref = self._resolve_local(search_ref, version_range)
        if not resolved_ref or self._conan_app.update:
            remote_resolved_ref, remote_name = self._resolve_remote(search_ref, version_range)
            resolved_ref = self._resolve_version(version_range, [resolved_ref, remote_resolved_ref])

        origin = f"remote '{remote_name}'" if resolved_ref == remote_resolved_ref and remote_name \
            else "local cache"

        if resolved_ref:
            self._result.append("Version range '%s' required by '%s' resolved to '%s' in %s"
                                % (version_range, base_conanref, str(resolved_ref), origin))
            require.ref = resolved_ref
        else:
            raise ConanException("Version range '%s' from requirement '%s' required by '%s' "
                                 "could not be resolved in %s"
                                 % (version_range, require, base_conanref, origin))
        return resolved_ref

    def _resolve_local(self, search_ref, version_range):
        local_found = self._cached_cache.get(search_ref)
        if local_found is None:
            local_found = search_recipes(self._cache, search_ref)
            local_found = [ref for ref in local_found
                           if ref.user == search_ref.user and ref.channel == search_ref.channel]
            self._cached_cache[search_ref] = local_found
        if local_found:
            return self._resolve_version(version_range, local_found)

    def _search_and_resolve_remotes(self, search_ref, version_range):
        results = []
        remotes = self._conan_app.enabled_remotes
        selected_remote = self._conan_app.selected_remote
        for remote in remotes:
            if not selected_remote or remote == selected_remote:
                remote_results = self._search_remote_recipes(remote, search_ref)
                remote_results = [ref for ref in remote_results
                                  if ref.user == search_ref.user
                                  and ref.channel == search_ref.channel]
                resolved_version = self._resolve_version(version_range, remote_results)
                if resolved_version and not self._conan_app.update:
                    return resolved_version, remote.name
                elif resolved_version:
                    results.append({"remote": remote.name,
                                    "version": resolved_version})
        if len(results) > 0:
            resolved_version = self._resolve_version(version_range,
                                                     [result.get("version") for result in results])
            for result in results:
                if result.get("version") == resolved_version:
                    return result.get("version"), result.get("remote")
        else:
            return None, None

    def _resolve_remote(self, search_ref, version_range):
        # Searching for just the name is much faster in remotes like Artifactory
        resolved_ref, remote_name = self._search_and_resolve_remotes(search_ref, version_range)
        if resolved_ref:
            self._result.append("%s versions found in '%s' remote" % (search_ref, remote_name))
        else:
            self._result.append("%s versions not found in remotes")
        # We don't want here to resolve the revision that should be done in the proxy
        # as any other regular flow
        # FIXME: refactor all this and update for 2.0
        resolved_ref = resolved_ref.copy_clear_rev() if resolved_ref else None
        return (resolved_ref, remote_name) if resolved_ref else (None, None)

    def _resolve_version(self, version_range, refs_found):
        versions = {ref.version: ref for ref in refs_found if ref}
        result = satisfying(versions, version_range, self._result)
        return versions.get(result)
