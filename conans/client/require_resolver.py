from conans.model.ref import ConanFileReference
from conans.errors import ConanException
import re


def satisfying(list_versions, versionexpr, output):
    """ returns the maximum version that satisfies the expression
    if some version cannot be converted to loose SemVer, it is discarded with a msg
    This provides some woraround for failing comparisons like "2.1" not matching "<=2.1"
    """
    from semver import SemVer, max_satisfying
    version_range = versionexpr.replace(",", " ")
    candidates = {}
    for v in list_versions:
        try:
            ver = SemVer(v, loose=True)
            if not ver.prerelease:  # Hack to allow version "2.1" match expr "<=2.1"
                ver.prerelease = [0]
            candidates[ver] = v
        except (ValueError, AttributeError):
            output.warn("Version '%s' is not semver, cannot be compared with a range" % str(v))
    result = max_satisfying(candidates, version_range, loose=True)
    return candidates.get(result)


class RequireResolver(object):
    expr_pattern = re.compile("")

    def __init__(self, output, local_search, remote_search):
        self._output = output
        self._local_search = local_search
        self._remote_search = remote_search

    def resolve(self, require, base_conanref):
        version_range = require.version_range
        if version_range is None:
            return

        if require.is_resolved:
            ref = require.conan_reference
            resolved = self._resolve_version(version_range, [ref])
            if not resolved:
                self._output.werror("Version range '%s' required by '%s' not valid for "
                                    "downstream requirement '%s'"
                                    % (version_range, base_conanref, str(ref)))
            else:
                self._output.success("Version range '%s' required by '%s' valid for "
                                     "downstream requirement '%s'"
                                     % (version_range, base_conanref, str(ref)))
            return

        ref = require.conan_reference
        # The search pattern must be a string
        search_ref = str(ConanFileReference(ref.name, "*", ref.user, ref.channel))
        resolved = self._resolve_local(search_ref, version_range)
        if not resolved:
            remote_found = self._remote_search.search_remotes(search_ref)
            if remote_found:
                resolved = self._resolve_version(version_range, remote_found)

        if resolved:
            self._output.success("Version range '%s' required by '%s' resolved to '%s'"
                                 % (version_range, base_conanref, str(resolved)))
            require.conan_reference = resolved
        else:
            raise ConanException(
                "The version in '%s' from requirement '%s' could not be resolved" % (version_range, require))

    def _resolve_local(self, search_ref, version_range):
        if self._local_search:
            local_found = self._local_search.search(search_ref)
            if local_found:
                resolved_version = self._resolve_version(version_range, local_found)
                if resolved_version:
                    return resolved_version

    def _resolve_version(self, version_range, local_found):
        versions = {ref.version: ref for ref in local_found}
        result = satisfying(versions, version_range, self._output)
        return versions.get(result)
