import fnmatch

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
                raise ConanException(f"Package ID '{self.raw}' not found")
        return prefs

    def filter_prevs(self, prevs):
        prevs = [p for p in prevs if fnmatch.fnmatch(p.revision, self.prev)]
        if not prevs:
            refs_str = f'{self.ref}#{self.rrev}:{self.package_id}#{self.prev}'
            if "*" not in refs_str:
                raise ConanException(f"Package revision '{self.raw}' not found")
        return prevs
