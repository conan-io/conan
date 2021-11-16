from functools import total_ordering

from conans.errors import ConanException
from conans.util.dates import timestamp_to_str


@total_ordering
class Version:
    """
    This is NOT an implementation of semver, as users may use any pattern in their versions.
    It is just a helper to parse "." or "-" and compare taking into account integers when possible
    """
    def __init__(self, value):
        assert isinstance(value, str)
        self._value = value
        self._items = None  # elements of the version
        self._pre = None
        self._build = None

    def bump(self, index):
        """
           Increments by 1 the version field at the specified index, setting to 0 the fields on the right.
           2.5 => bump(1) => 2.6
           1.5.7 => bump(0) => 2.0.0
        """
        if self._items is None:  # the indicator parse is needed if empty items
            self._parse()
        items = self._items.copy()
        try:
            items[index] += 1
        except TypeError:
            raise ConanException("Cannot bump version index {index}, not an int")
        for i in range(index+1, len(items)):
            items[i] = 0
        v = ".".join(str(i) for i in items)
        if self._pre:
            v += f"-{self._pre}"
        if self._build:
            v += f"+{self._build}"
        result = Version(v)
        result._items = items
        result._pre = self._pre
        result._build = self._build
        return result

    @property
    def pre(self):
        if self._items is None:  # the indicator parse is needed is empty items
            self._parse()
        return self._pre

    @property
    def build(self):
        if self._items is None:  # the indicator parse is needed is empty items
            self._parse()
        return self._build

    @property
    def main(self):
        if self._items is None:
            self._parse()
        return self._items

    @property
    def major(self):
        try:
            return self.main[0]
        except IndexError:
            return None

    @property
    def minor(self):
        try:
            return self.main[1]
        except IndexError:
            return None

    @property
    def patch(self):
        try:
            return self.main[2]
        except IndexError:
            return None

    def __str__(self):
        return self._value

    def __repr__(self):
        return self._value

    def __eq__(self, other):
        if not isinstance(other, Version):
            return self._value == other  # Assume the other is string like
        return self._value == other._value

    def __hash__(self):
        return hash(self._value)

    def __lt__(self, other):
        if not isinstance(other, Version):
            other = Version(other)
        if self.pre:
            if other.pre:  # both are pre-releases
                return (self.main, self.pre, self.build) < (other.main, other.pre, other.build)
            else:  # Left hand is pre-release, right side is regular
                if self.main == other.main:  # Problem only happens if both are equal
                    return True
                else:
                    return self.main < other.main
        else:
            if other.pre:  # Left hand is regular, right side is pre-release
                if self.main == other.main:  # Problem only happens if both are equal
                    return False
                else:
                    return self.main < other.main
            else:  # None of them is pre-release
                return (self.main, self.build) < (other.main, other.build)

    def _parse(self):
        items = self._value.rsplit("+", 1)  # split for build
        if len(items) == 2:
            value, build = items
            self._build = Version(build)  # This is a nested version by itself
        else:
            value = items[0]

        items = value.rsplit("-", 1)  # split for pre-release
        if len(items) == 2:
            value, pre = items
            self._pre = Version(pre)  # This is a nested version by itself
        else:
            value = items[0]
        items = value.split(".")
        items = [int(item) if item.isdigit() else item for item in items]
        self._items = items


@total_ordering
class RecipeReference:
    """ an exact (no version-range, no alias) reference of a recipe.
    Should be enough to locate a recipe in the cache or in a server
    Validation will be external to this class, at specific points (export, api, etc)
    """

    def __init__(self, name=None, version=None, user=None, channel=None, revision=None,
                 timestamp=None):
        self.name = name
        if version is not None and not isinstance(version, Version):
            version = Version(version)
        self.version = version  # This MUST be a version if we want to be able to order
        self.user = user
        self.channel = channel
        self.revision = revision
        self.timestamp = timestamp

    def __repr__(self):
        """ long repr like pkg/0.1@user/channel#rrev%timestamp """
        result = self.repr_notime()
        if self.timestamp is not None:
            result += "%{}".format(self.timestamp)
        return result

    def repr_notime(self):
        result = self.__str__()
        if self.revision is not None:
            result += "#{}".format(self.revision)
        return result

    def repr_humantime(self):
        result = self.repr_notime()
        assert self.timestamp
        result += " ({})".format(timestamp_to_str(self.timestamp))
        return result

    def __str__(self):
        """ shorter representation, excluding the revision and timestamp """
        if self.name is None:
            return ""
        result = "/".join([self.name, str(self.version)])
        if self.user:
            result += "@{}".format(self.user)
        if self.channel:
            assert self.user
            result += "/{}".format(self.channel)
        return result

    def __lt__(self, ref):
        # The timestamp goes before the revision for ordering revisions chronologically
        # In theory this is enough for sorting
        return (self.name, self.version, self.user or "", self.channel or "", self.timestamp,
                self.revision) \
               < (ref.name, ref.version, ref.user or "", ref.channel or "", ref.timestamp,
                  ref.revision)

    def __eq__(self, ref):
        # Timestamp doesn't affect equality.
        # This is necessary for building an ordered list of UNIQUE recipe_references for Lockfile
        if ref is None:
            return False
        return (self.name, self.version, self.user, self.channel, self.revision) == \
               (ref.name, ref.version, ref.user, ref.channel, ref.revision)

    def __hash__(self):
        # This is necessary for building an ordered list of UNIQUE recipe_references for Lockfile
        return hash((self.name, self.version, self.user, self.channel, self.revision))

    @staticmethod
    def loads(rref):  # TODO: change this default to validate only on end points
        try:
            # timestamp
            tokens = rref.rsplit("%", 1)
            text = tokens[0]
            timestamp = float(tokens[1]) if len(tokens) == 2 else None

            # revision
            tokens = text.split("#", 1)
            ref = tokens[0]
            revision = tokens[1] if len(tokens) == 2 else None

            # name, version always here
            tokens = ref.split("@", 1)
            name, version = tokens[0].split("/", 1)
            assert name and version
            # user and channel
            if len(tokens) == 2 and tokens[1]:
                tokens = tokens[1].split("/", 1)
                user = tokens[0] if tokens[0] else None
                channel = tokens[1] if len(tokens) == 2 else None
            else:
                user = channel = None
            return RecipeReference(name, version, user, channel, revision, timestamp)
        except Exception:
            from conans.errors import ConanException
            raise ConanException(
                f"{rref} is not a valid recipe reference, provide a reference"
                f" in the form name/version[@user/channel]")
