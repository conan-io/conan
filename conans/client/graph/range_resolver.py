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


class RangeResolver(object):

    def __init__(self, cache, remote_manager):
        self._cache = cache
        self._remote_manager = remote_manager
        self._cached_remote_found = {}
        self._result = []

    @property
    def output(self):
        return self._result

    def clear_output(self):
        self._result = []

    def resolve(self, require, base_conanref, update, remotes):
        version_range = require.version_range
        if version_range is None:
            return

        if require.is_resolved:
            ref = require.ref
            resolved_ref = self._resolve_version(version_range, [ref])
            if not resolved_ref:
                raise ConanException("Version range '%s' required by '%s' not valid for "
                                     "downstream requirement '%s'"
                                     % (version_range, base_conanref, str(ref)))
            else:
                self._result.append("Version range '%s' required by '%s' valid for "
                                    "downstream requirement '%s'"
                                    % (version_range, base_conanref, str(ref)))
            return

        ref = require.ref
        # The search pattern must be a string
        search_ref = ConanFileReference(ref.name, "*", ref.user, ref.channel)

        if update:
            resolved_ref, remote_name = self._resolve_remote(search_ref, version_range, remotes)
            if not resolved_ref:
                remote_name = None
                resolved_ref = self._resolve_local(search_ref, version_range)
        else:
            remote_name = None
            resolved_ref = self._resolve_local(search_ref, version_range)
            if not resolved_ref:
                resolved_ref, remote_name = self._resolve_remote(search_ref, version_range, remotes)

        origin = ("remote '%s'" % remote_name) if remote_name else "local cache"
        if resolved_ref:
            self._result.append("Version range '%s' required by '%s' resolved to '%s' in %s"
                                % (version_range, base_conanref, str(resolved_ref), origin))
            require.ref = resolved_ref
        else:
            raise ConanException("Version range '%s' from requirement '%s' required by '%s' "
                                 "could not be resolved in %s"
                                 % (version_range, require, base_conanref, origin))

    def _resolve_local(self, search_ref, version_range):
        local_found = search_recipes(self._cache, search_ref)
        local_found = [ref for ref in local_found
                       if ref.user == search_ref.user and
                       ref.channel == search_ref.channel]
        if local_found:
            return self._resolve_version(version_range, local_found)

    def _search_remotes(self, search_ref, remotes):
        pattern = str(search_ref)
        for remote in remotes.values():
            if not remotes.selected or remote == remotes.selected:
                result = self._remote_manager.search_recipes(remote, pattern, ignorecase=False)
                result = [ref for ref in result
                          if ref.user == search_ref.user and ref.channel == search_ref.channel]
                if result:
                    return result, remote.name
        return None, None

    def _resolve_remote(self, search_ref, version_range, remotes):
        # We should use ignorecase=False, we want the exact case!
        found_refs, remote_name = self._cached_remote_found.get(search_ref, (None, None))
        if found_refs is None:
            # Searching for just the name is much faster in remotes like Artifactory
            found_refs, remote_name = self._search_remotes(search_ref, remotes)
            if found_refs:
                self._result.append("%s versions found in '%s' remote" % (search_ref, remote_name))
            else:
                self._result.append("%s versions not found in remotes")
            # We don't want here to resolve the revision that should be done in the proxy
            # as any other regular flow
            found_refs = [ref.copy_clear_rev() for ref in found_refs or []]
            # Empty list, just in case it returns None
            self._cached_remote_found[search_ref] = found_refs, remote_name
        if found_refs:
            return self._resolve_version(version_range, found_refs), remote_name
        return None, None

    def _resolve_version(self, version_range, refs_found):
        versions = {ref.version: ref for ref in refs_found}
        result = satisfying(versions, version_range, self._result)
        return versions.get(result)
