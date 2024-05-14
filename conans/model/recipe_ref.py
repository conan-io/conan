
import fnmatch
import re
from functools import total_ordering

from conans.errors import ConanException
from conans.model.version import Version
from conans.util.dates import timestamp_to_str


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

    def repr_reduced(self):
        result = self.__str__()
        if self.revision is not None:
            result += "#{}".format(self.revision[0:4])
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
        # When no timestamp is given, it will always have lower priority, to avoid comparison
        # errors float <> None
        return (self.name, self.version, self.user or "", self.channel or "", self.timestamp or 0,
                self.revision or "") \
               < (ref.name, ref.version, ref.user or "", ref.channel or "", ref.timestamp or 0,
                  ref.revision or "")

    def __eq__(self, ref):
        # Timestamp doesn't affect equality.
        # This is necessary for building an ordered list of UNIQUE recipe_references for Lockfile
        if ref is None:
            return False
        # If one revision is not defined, they are equal
        if self.revision is not None and ref.revision is not None:
            return (self.name, self.version, self.user, self.channel, self.revision) == \
                   (ref.name, ref.version, ref.user, ref.channel, ref.revision)
        return (self.name, self.version, self.user, self.channel) == \
               (ref.name, ref.version, ref.user, ref.channel)

    def __hash__(self):
        # This is necessary for building an ordered list of UNIQUE recipe_references for Lockfile
        return hash((self.name, self.version, self.user, self.channel))

    @staticmethod
    def loads(rref):
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

    def validate_ref(self, allow_uppercase=False):
        """ at the moment only applied to exported (exact) references, but not for requires
        that could contain version ranges
        """
        from conan.api.output import ConanOutput
        self_str = str(self)
        if self_str != self_str.lower():
            if not allow_uppercase:
                raise ConanException(f"Conan packages names '{self_str}' must be all lowercase")
            else:
                ConanOutput().warning(f"Package name '{self_str}' has uppercase, and has been "
                                      "allowed by temporary config. This will break in later 2.X")
        if len(self_str) > 200:
            raise ConanException(f"Package reference too long >200 {self_str}")
        if ":" in repr(self):
            raise ConanException(f"Invalid recipe reference '{repr(self)}' is a package reference")
        if not allow_uppercase:
            validation_pattern = re.compile(r"^[a-z0-9_][a-z0-9_+.-]{1,100}\Z")
        else:
            validation_pattern = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_+.-]{1,100}\Z")
        if validation_pattern.match(self.name) is None:
            raise ConanException(f"Invalid package name '{self.name}'")
        if validation_pattern.match(str(self.version)) is None:
            raise ConanException(f"Invalid package version '{self.version}'")
        if self.user and validation_pattern.match(self.user) is None:
            raise ConanException(f"Invalid package user '{self.user}'")
        if self.channel and validation_pattern.match(self.channel) is None:
            raise ConanException(f"Invalid package channel '{self.channel}'")

         # Warn if they use .+ in the name/user/channel, as it can be problematic for generators
        pattern = re.compile(r'[.+]')
        if pattern.search(self.name):
            ConanOutput().warning(f"Name containing special chars is discouraged '{self.name}'")
        if self.user and pattern.search(self.user):
            ConanOutput().warning(f"User containing special chars is discouraged '{self.user}'")
        if self.channel and pattern.search(self.channel):
            ConanOutput().warning(f"Channel containing special chars is discouraged "
                                  f"'{self.channel}'")

    def matches(self, pattern, is_consumer):
        negate = False
        if pattern.startswith("!") or pattern.startswith("~"):
            pattern = pattern[1:]
            negate = True

        no_user_channel = False
        if pattern.endswith("@"):  # it means we want to match only without user/channel
            pattern = pattern[:-1]
            no_user_channel = True
        elif "@#" in pattern:
            pattern = pattern.replace("@#", "#")
            no_user_channel = True

        condition = ((pattern == "&" and is_consumer) or
                      fnmatch.fnmatchcase(str(self), pattern) or
                      fnmatch.fnmatchcase(self.repr_notime(), pattern))
        if no_user_channel:
            condition = condition and not self.user and not self.channel
        if negate:
            return not condition
        return condition


def ref_matches(ref, pattern, is_consumer):
    if not ref or not str(ref):
        assert is_consumer
        ref = RecipeReference.loads("*/*")  # FIXME: ugly
    return ref.matches(pattern, is_consumer=is_consumer)
