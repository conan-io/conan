from collections import defaultdict
from conans.errors import ConanException


class Scope(set):
    """ the set of possible scopes than a package can have, by name(string):
    "dev", "test", "myscope"...
    it is just a set, but with syntax to be queried as:
       if self.scope.dev:
    """

    def __getattr__(self, field):
        if field in self:
            return True
        return False


# This is necessary, as None cannot be ordered in Py3
_root = "CONAN_ROOT*"


class Scopes(defaultdict):
    """ all the scopes of a dependency graph, as a dict{package name(str): Scope
    the root package of the graph might not have name, then its key is None.
    It is loaded and saved to text as:
        Package1:dev
        Package1:test
        Package2:dev
        dev  # for the root package, without name
        other # any name allowed
    This will be stored in memory as {Package1: Scopes(set[dev, test]),
                                      Package2: Scopes(...),
                                      None: Scopes(set[dev, other])
    To be able to remove the "dev" scope from the root package (set by default), the "!dev"
    syntax is provided
    """
    def __init__(self):
        super(Scopes, self).__init__(Scope)
        self[_root].add("dev")

    @staticmethod
    def from_list(items):
        result = Scopes()
        for item in items:
            chunks = item.split(":")
            if len(chunks) == 2:
                result[chunks[0]].add(chunks[1])
            elif len(chunks) == 1:
                result[_root].add(item)
            else:
                raise ConanException("Bad scope %s" % item)
        if "!dev" in result[_root]:
            result[_root].remove("!dev")
            result[_root].remove("dev")
        return result

    @property
    def root(self):
        return self[_root]

    @staticmethod
    def loads(text):
        return Scopes.from_list([s.strip() for s in text.splitlines()])

    def dumps(self):
        result = []
        for name, scopes in sorted(self.items()):
            if name != _root:
                result.extend("%s:%s" % (name, s) for s in sorted(scopes))
            else:
                result.extend(sorted(scopes))
        return "\n".join(result)
