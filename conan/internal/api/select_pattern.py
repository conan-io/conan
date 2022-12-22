import fnmatch
from enum import Enum

from conans.errors import ConanException


class SelectPattern:

    def __init__(self, expression, rrev="latest", prev="latest"):
        def split(s, c, default=None):
            if not s:
                return None, default
            tokens = s.split(c, 1)
            if len(tokens) == 2:
                return tokens[0], tokens[1] or default
            return tokens[0], default

        recipe, package = split(expression, ":")
        self.raw = expression
        self.ref, rrev = split(recipe, "#", rrev)
        ref, user_channel = split(self.ref, "@")
        self.name, self.version = split(ref, "/")
        self.user, self.channel = split(user_channel, "/")
        self.rrev, _ = split(rrev, "%")
        self.package_id, prev = split(package, "#", prev)
        self.prev, _ = split(prev, "%")

    @property
    def is_latest_rrev(self):
        return self.rrev == "latest"

    @property
    def is_latest_prev(self):
        return self.prev == "latest"

    def check_refs(self, refs):
        if not refs and self.ref and "*" not in self.ref:
            raise ConanException(f"Recipe '{self.ref}' not found")

    def filter_rrevs(self, rrevs):
        rrevs = [r for r in rrevs if fnmatch.fnmatch(r.revision, self.rrev)]
        if not rrevs:
            refs_str = f'{self.ref}#{self.rrev}'
            if "*" not in refs_str:
                raise ConanException(f"Recipe revision '{refs_str}' not found")
        return rrevs

    def filter_prefs(self, prefs):
        prefs = [p for p in prefs if fnmatch.fnmatch(p.package_id, self.package_id)]
        if not prefs:
            refs_str = f'{self.ref}#{self.rrev}:{self.package_id}'
            if "*" not in refs_str:
                raise ConanException(f"Package ID '{refs_str}' not found")
        return prefs

    def filter_prevs(self, prevs):
        prevs = [p for p in prevs if fnmatch.fnmatch(p.revision, self.prev)]
        if not prevs:
            refs_str = f'{self.ref}#{self.rrev}:{self.package_id}#{self.prev}'
            if "*" not in refs_str:
                raise ConanException(f"Package revision '{refs_str}' not found")
        return prevs


class ListPatternMode(Enum):
    SHOW_REFS = 1
    SHOW_LATEST_RREV = 2
    SHOW_LATEST_PREV = 3
    SHOW_PACKAGE_IDS = 4
    SHOW_ALL_RREVS = 5
    SHOW_ALL_PREVS = 6
    UNDEFINED = 7


class ListPattern(SelectPattern):

    @property
    def mode(self):
        no_regex = "*" not in self.raw
        if no_regex:
            # FIXME: now, the server is returning for "conan search zlib" all the zlib versions,
            #        but "conan search zli" is raising and error. Inconsistency?
            if not (self.name and self.version):
                # # zlib (server is going to get all the versions for zlib)
                if self.package_id is None:
                    return ListPatternMode.SHOW_REFS
                # zlib:PID -> it will fail on server side! Nothing to do here
            else:
                if self.package_id is None:
                    # zlib/1.2.11
                    if self.is_latest_rrev:
                        return ListPatternMode.SHOW_LATEST_RREV
                    # zlib/1.2.11#RREV
                    elif self.rrev:
                        return ListPatternMode.SHOW_PACKAGE_IDS
                else:
                    # zlib/1.2.11#RREV:PID | zlib/1.2.11#RREV:PID#PREV
                    if self.is_latest_prev or self.prev:
                        return ListPatternMode.SHOW_LATEST_PREV
        else:
            if self.package_id is None:
                # zlib/* | zlib*
                if self.is_latest_rrev:
                    return ListPatternMode.SHOW_REFS
                # zlib/1.2.11#*
                elif "*" in self.rrev:
                    return ListPatternMode.SHOW_ALL_RREVS
            else:
                # zlib/1.2.11#latest:* | zlib/1.2.11#RREV:*
                if self.is_latest_prev:
                    return ListPatternMode.SHOW_PACKAGE_IDS
                # zlib/1.2.11#latest:*#* | zlib/1.2.11#RREV:PID#*
                elif "*" in self.prev:
                    return ListPatternMode.SHOW_ALL_PREVS
        return ListPatternMode.UNDEFINED
