class Version(str):
    SEP = '.'

    def __new__(cls, content):
        return str.__new__(cls, content.strip())

    @property
    def as_list(self):
        result = []
        for item in self.split(Version.SEP):
            result.append(int(item) if item.isdigit() else item)
        return result

    def major(self, fill=True):
        self_list = self.as_list
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
        v0 = str(self_list[0]) if len(self_list) > 0 else "0"
        v1 = str(self_list[1]) if len(self_list) > 1 else "0"
        if fill:
            return Version(".".join([v0, v1, 'Z']))
        return Version(".".join([v0, v1]))

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

        for ind, el in enumerate(self.as_list):
            if ind + 1 > len(other.as_list):
                return 1
            if not isinstance(el, int) and isinstance(other.as_list[ind], int):
                # Version compare with 1.4.rc2
                return -1
            elif not isinstance(other.as_list[ind], int) and isinstance(el, int):
                return 1
            elif el == other.as_list[ind]:
                continue
            elif el > other.as_list[ind]:
                return 1
            else:
                return -1
        if len(other.as_list) > len(self.as_list):
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
