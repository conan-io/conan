import re
from functools import total_ordering

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.util.dates import from_timestamp_to_iso8601


@total_ordering
class Version:
    """
    This is NOT an implementation of semver, as users may use any pattern in their versions.
    It is just a helper to parse "." or "-" and compare taking into account integers when possible
    """
    # FIXME: parse also +
    version_pattern = re.compile('[.-]')

    def __init__(self, value):
        assert isinstance(value, str)
        self._value = value
        self._items = None  # elements of the version

    def __str__(self):
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
        # FIXME: this comparison is not enough
        return self._tokens() < other._tokens()

    def _tokens(self):
        if self._items is None:
            items = self.version_pattern.split(self._value)
            items = [int(item) if item.isdigit() else item for item in items]
            self._items = items
        return self._items


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
        self.timestamp = timestamp  # integer, seconds from 0 in UTC

    @staticmethod
    def from_conanref(ref, timestamp=None):
        return RecipeReference(ref.name, ref.version, ref.user, ref.channel, ref.revision, timestamp)

    def to_conanfileref(self):
        return ConanFileReference(self.name, str(self.version), self.user, self.channel,
                                  self.revision)

    def __repr__(self):
        """ long repr like pkg/0.1@user/channel#rrev%timestamp """
        result = self.__str__()
        if self.revision is not None:
            result += "#{}".format(self.revision)
        if self.timestamp is not None:
            result += "%{}".format(self.timestamp)
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

    def format_time(self):
        """ same as repr(), but with human readable time """
        result = self.__str__()
        if self.revision is not None:
            result += "#{}".format(self.revision)
        if self.timestamp is not None:
            # TODO: Improve the time format
            result += "({})".format(from_timestamp_to_iso8601(self.timestamp))
        return result

    def __lt__(self, ref):
        # The timestamp goes before the revision for ordering revisions chronologically
        # In theory this is enough for sorting
        return (self.name, self.version, self.user, self.channel, self.timestamp, self.revision) \
               < (ref.name, ref.version, ref.user, ref.channel, ref.timestamp, ref.revision)

    def __eq__(self, ref):
        # Timestamp doesn't affect equality.
        # This is necessary for building an ordered list of UNIQUE recipe_references for Lockfile
        return (self.name, self.version, self.user, self.channel, self.revision) \
               == (ref.name, ref.version, ref.user, ref.channel, ref.revision)

    def __hash__(self):
        # This is necessary for building an ordered list of UNIQUE recipe_references for Lockfile
        return hash((self.name, self.version, self.user, self.channel, self.revision))

    @staticmethod
    def loads(text):  # TODO: change this default to validate only on end points
        try:
            # timestamp
            tokens = text.rsplit("%", 1)
            text = tokens[0]
            timestamp = int(tokens[1]) if len(tokens) == 2 else None

            # revision
            tokens = text.split("#", 1)
            ref = tokens[0]
            revision = tokens[1] if len(tokens) == 2 else None

            # name, version always here
            tokens = ref.split("@", 1)
            name, version = tokens[0].split("/", 1)
            assert name and version
            # user and channel
            if len(tokens) == 2:
                tokens = tokens[1].split("/", 1)
                user = tokens[0]
                channel = tokens[1] if len(tokens) == 2 else None
            else:
                user = channel = None
            return RecipeReference(name, version, user, channel, revision, timestamp)
        except Exception:
            raise ConanException(
                f"{text} is not a valid recipe reference, provide a reference"
                f" in the form name/version[@user/channel]")
