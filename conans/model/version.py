import re


class Version(str):
    """ This is NOT an implementation of semver, as users may use any pattern in their versions.
    It is just a helper to parse .-, and compare taking into account integers when possible
    """
    version_pattern = re.compile('[.-]')

    def __new__(cls, content):
        return str.__new__(cls, content.strip())

    @property
    def as_list(self):
        if not hasattr(self, "_cached_list"):
            tokens = self.rsplit('+', 1)
            self._base = tokens[0]
            if len(tokens) == 2:
                self._build = tokens[1]
            self._cached_list = []
            tokens = Version.version_pattern.split(tokens[0])
            for item in tokens:
                self._cached_list.append(int(item) if item.isdigit() else item)
        return self._cached_list

    def major(self, fill=True):
        self_list = self.as_list
        if not isinstance(self_list[0], int):
            return self._base
        v = str(self_list[0]) if self_list else "0"
        if fill:
            return Version(".".join([v, 'Y', 'Z']))
        return Version(v)

    def stable(self):
        """ same as major, but as semver, 0.Y.Z is not considered
        stable, so return it as is
        """
        if self.as_list[0] == 0:
            return self
        return self.major()

    def minor(self, fill=True):
        self_list = self.as_list
        if not isinstance(self_list[0], int):
            return self._base
        v0 = str(self_list[0]) if len(self_list) > 0 else "0"
        v1 = str(self_list[1]) if len(self_list) > 1 else "0"
        if fill:
            return Version(".".join([v0, v1, 'Z']))
        return Version(".".join([v0, v1]))

    def patch(self):
        self_list = self.as_list
        if not isinstance(self_list[0], int):
            return self._base
        v0 = str(self_list[0]) if len(self_list) > 0 else "0"
        v1 = str(self_list[1]) if len(self_list) > 1 else "0"
        v2 = str(self_list[2]) if len(self_list) > 2 else "0"
        return Version(".".join([v0, v1, v2]))

    def pre(self):
        self_list = self.as_list
        if not isinstance(self_list[0], int):
            return self._base
        v0 = str(self_list[0]) if len(self_list) > 0 else "0"
        v1 = str(self_list[1]) if len(self_list) > 1 else "0"
        v2 = str(self_list[2]) if len(self_list) > 2 else "0"
        v = ".".join([v0, v1, v2])
        if len(self_list) > 3:
            v += "-%s" % self_list[3]
        return Version(v)

    @property
    def build(self):
        if hasattr(self, "_build"):
            return self._build
        return ""

    @property
    def base(self):
        self.as_list
        return Version(self._base)

    def compatible(self, other):
        if not isinstance(other, Version):
            other = Version(other)
        for v1, v2 in zip(self.as_list, other.as_list):
            if v1 in ["X", "Y", "Z"] or v2 in ["X", "Y", "Z"]:
                return True
            if v1 != v2:
                return False
        return True

    def __cmp__(self, other):
        if other is None:
            return 1
        if not isinstance(other, Version):
            other = Version(other)

        other_list = other.as_list
        for ind, el in enumerate(self.as_list):
            if ind + 1 > len(other_list):
                if isinstance(el, int):
                    return 1
                return -1
            if not isinstance(el, int) and isinstance(other_list[ind], int):
                # Version compare with 1.4.rc2
                return -1
            elif not isinstance(other_list[ind], int) and isinstance(el, int):
                return 1
            elif el == other_list[ind]:
                continue
            elif el > other_list[ind]:
                return 1
            else:
                return -1
        if len(other_list) > len(self.as_list):
            return -1
        else:
            return 0

    def __gt__(self, other):
        return self.__cmp__(other) == 1

    def __lt__(self, other):
        return self.__cmp__(other) == -1

    def __le__(self, other):
        return self.__cmp__(other) in [0, -1]

    def __ge__(self, other):
        return self.__cmp__(other) in [0, 1]
