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

        items = value.rsplit("+", 1)  # split for build
        if len(items) == 2:
            value, build = items
            self._build = Version(build)  # This is a nested version by itself
        else:
            value = items[0]
            self._build = None

        items = value.rsplit("-", 1)  # split for pre-release
        if len(items) == 2:
            value, pre = items
            self._pre = Version(pre)  # This is a nested version by itself
        else:
            value = items[0]
            self._pre = None
        items = value.split(".")
        items = [int(item) if item.isdigit() else item for item in items]
        self._items = items
        self._nonzero_items = items.copy()
        while self._nonzero_items[-1] == 0:
            del self._nonzero_items[-1]

    def bump(self, index):
        """
           Increments by 1 the version field at the specified index, setting to 0 the fields on the right.
           2.5 => bump(1) => 2.6
           1.5.7 => bump(0) => 2.0.0
        """
        # this method is used to compute version ranges from tilde ~1.2 and caret ^1.2.1 ranges
        # TODO: at this moment it only works for digits, cannot increment pre-release or builds
        # better not make it public yet, keep it internal
        items = self._items.copy()
        try:
            items[index] += 1
        except TypeError:
            raise ConanException("Cannot bump version index {index}, not an int")
        for i in range(index+1, len(items)):
            items[i] = 0
        v = ".".join(str(i) for i in items)
        # prerelease and build are dropped while bumping digits
        result = Version(v)
        result._items = items
        return result

    @property
    def pre(self):
        return self._pre

    @property
    def build(self):
        return self._build

    @property
    def main(self):
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
        if other is None:
            return False
        if not isinstance(other, Version):
            other = Version(other)

        return (self._nonzero_items, self._pre, self._build) ==\
               (other._nonzero_items, other._pre, other._build)

    def __hash__(self):
        return hash((self._nonzero_items, self._pre, self._build))

    def __lt__(self, other):
        if other is None:
            return False
        if not isinstance(other, Version):
            other = Version(other)

        if self._pre:
            if other._pre:  # both are pre-releases
                return (self._nonzero_items, self._pre, self._build) < \
                       (other._nonzero_items, other._pre, other._build)
            else:  # Left hand is pre-release, right side is regular
                if self._nonzero_items == other._nonzero_items:  # Problem only happens if both equal
                    return True
                else:
                    return self._nonzero_items < other._nonzero_items
        else:
            if other._pre:  # Left hand is regular, right side is pre-release
                if self._nonzero_items == other._nonzero_items:  # Problem only happens if both equal
                    return False
                else:
                    return self._nonzero_items < other._nonzero_items
            else:  # None of them is pre-release
                return (self._nonzero_items, self._build) < (other._nonzero_items, other._build)


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
