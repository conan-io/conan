# -*- coding: utf-8 -*-
from six.moves import configparser

from conans.client.graph.range_resolver import RangeResolver
from conans.errors import ConanException


class RangeResolverLocked(RangeResolver):
    """RangeResolver with version locking mechanism."""

    def __init__(self, lockfile, lock, *args, **kwargs):
        super(RangeResolverLocked, self).__init__(*args, **kwargs)
        self._lockfile = lockfile
        self._lock = lock

        self._lockfile_config = configparser.ConfigParser()
        self._lockfile_config.optionxform = str
        try:
            self._lockfile_config.read(self._lockfile)
        except configparser.Error as e:
            raise ConanException("Error parsing lockfile: %s\n%s" % (self._lockfile, str(e)))
        self._pinned_versions = self._lockfile_config.defaults()

    def flush(self):
        if self._lock:
            with open(self._lockfile, "w") as lockfile:
                self._lockfile_config.write(lockfile)

    def resolve(self, require, base_conanref, update, remote_name):
        if not require.version_range and self._lock:
            self._set_version(require.ref)
            return

        was_not_resolved = not require.is_resolved
        super(RangeResolverLocked, self).resolve(
            require, base_conanref, update, remote_name
        )
        is_resolved = require.is_resolved

        if was_not_resolved and is_resolved and self._lock:
            self._set_version(require.ref)

    def _resolve_version(self, version_range, refs_found):
        if self._lock:
            return super(RangeResolverLocked, self)._resolve_version(
                version_range, refs_found
            )

        versions = {ref.version: ref for ref in refs_found}
        return versions.get(self._get_version(refs_found[0]))

    def _set_version(self, ref):
        self._pinned_versions[ref.name] = ref.version

    def _get_version(self, ref):
        try:
            return self._pinned_versions[ref.name]
        except KeyError:
            raise ConanException(
                "Cannot retrieve reference '{}' "
                "version from lock file '{}'. Update lockfile.".format(
                    ref.name, self._lockfile
                )
            )
