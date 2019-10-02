from functools import total_ordering

from conans.errors import ConanException


@total_ordering
class Cppstd(object):

    def __init__(self, value):
        self._version = str(value).strip()
        if self._version.startswith("gnu"):  # settings.compiler.cppstd e.g gnu17
            self._version = ''.join(filter(str.isdigit, str(value)))
        if not self._version:
            raise ConanException("Invalid version '{}'".format(value))

    def _compare(self, version):
        if self._version > version:
            return 1
        elif version > self._version:
            return -1
        else:
            return 0

    def __eq__(self, other):
        if not isinstance(other, Cppstd):
            other = Cppstd(other)
        return self._compare(other._version) == 0

    def __lt__(self, other):
        if not isinstance(other, Cppstd):
            other = Cppstd(other)
        return self._compare(other._version) < 0
