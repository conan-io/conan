# coding=utf-8

import re
from conans.errors import ConanException
from functools import total_ordering


version_pattern = re.compile(r'^(?:[\d]+\.){0,2}[\d]+$')


@total_ordering
class Version(object):
    major = minor = path = None

    def __init__(self, version_str):
        v = str(version_str).strip()
        if not version_pattern.match(v):
            raise ConanException("Version string '{}' not valid, it should be of the format"
                                 " '<major>.<minor>.<patch>', where each of the components"
                                 " is optional and can only contain numbers.".format(v))
        parts = iter(v.split('.'))
        self.major = next(parts)
        self.minor = next(parts, None)
        self.patch = next(parts, None)

    @staticmethod
    def _as_tuple(v):
        return (int(v.major), int(v.minor or 0), int(v.patch or 0))

    def __eq__(self, other):
        if not isinstance(other, Version):
            other = Version(other)
        return Version._as_tuple(self) == Version._as_tuple(other)

    def __lt__(self, other):
        if not isinstance(other, Version):
            other = Version(other)
        return Version._as_tuple(self) < Version._as_tuple(other)
