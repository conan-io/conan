# coding=utf-8

from functools import total_ordering

from semver import SemVer

from conans.errors import ConanException


@total_ordering
class Version(object):
    _semver = None
    loose = True  # Allow incomplete version strings like '1.2' or '1-dev0'

    def __init__(self, value):
        v = str(value).strip()
        try:
            self._semver = SemVer(v, loose=self.loose)
        except ValueError:
            raise ConanException("Invalid version '{}'".format(value))

    def __str__(self):
        return str(self._semver)

    @property
    def major(self):
        return str(self._semver.major)

    @property
    def minor(self):
        return str(self._semver.minor)

    @property
    def patch(self):
        return str(self._semver.patch)

    @property
    def prerelease(self):
        return str(".".join(map(str, self._semver.prerelease)))

    @property
    def build(self):
        return str(".".join(map(str, self._semver.build)))

    def __eq__(self, other):
        if not isinstance(other, Version):
            other = Version(other)
        return self._semver.compare(other._semver) == 0

    def __lt__(self, other):
        if not isinstance(other, Version):
            other = Version(other)
        return self._semver.compare(other._semver) < 0
