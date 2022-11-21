import fnmatch

from conans.errors import ConanException


class RefPattern:
    def __init__(self, expression, rrev=None, prev=None):

        def split(s, c, default=None):
            if not s:
                return None, default
            tokens = s.split(c, 1)
            if len(tokens) == 2:
                return tokens[0], tokens[1] or default
            return tokens[0], default

        recipe, package = split(expression, ":")
        self.ref, rrev = split(recipe, "#", rrev)
        self.rrev, _ = split(rrev, "%")
        self.package_id, prev = split(package, "#", prev)
        self.prev, _ = split(prev, "%")

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
