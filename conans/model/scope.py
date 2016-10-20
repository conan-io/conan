from collections import defaultdict
from conans.errors import ConanException


class Scope(dict):
    """ the set of possible scopes than a package can have, by name(string):
    "dev", "test", "myscope"...
    it is just a set, but with syntax to be queried as:
       if self.scope.dev:
    """

    def __getattr__(self, field):
        return self.get(field)

    def __setattr__(self, field, value):
        self[field] = value

    def __repr__(self):
        return ", ".join("%s=%s" % (k, v) for k, v in sorted(self.items()))


# This is necessary, as None cannot be ordered in Py3
_root = "0CONAN_ROOT*"
_all = "ALL"


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
    """
    def __init__(self):
        super(Scopes, self).__init__(Scope)
        self[_root].dev = True

    def package_scope(self, name=None):
        """ return the scopes for the given package which are the scopes set
        for ALL, updated (high priority) with the specific package scopes
        if the package name is None, then it is the ROOT package/consumer
        """
        scope = Scope(self.get(_all, {}))
        scope.update(self[name or _root])
        return scope

    @staticmethod
    def from_list(items):
        result = Scopes()
        for item in items:
            try:
                key, value = item.split("=")
            except:
                raise ConanException("Bad scope %s" % item)
            v = value.upper()
            if v == "TRUE":
                value = True
            elif v == "FALSE":
                value = False
            elif v == "NONE":
                value = None

            chunks = key.split(":")
            if len(chunks) == 2:
                root = chunks[0]
                scope = chunks[1]
            elif len(chunks) == 1:
                root = _root
                scope = chunks[0]
            else:
                raise ConanException("Bad scope %s" % item)

            result[root][scope] = value
        return result

    def update_scope(self, other):
        for name, scopes in other.items():
            self[name].update(scopes)

    @staticmethod
    def loads(text):
        return Scopes.from_list([s.strip() for s in text.splitlines()])

    def dumps(self):
        result = []
        for name, scopes in sorted(self.items()):
            if name != _root:
                result.extend("%s:%s=%s" % (name, k, v) for (k, v) in sorted(scopes.items()))
            else:
                result.extend("%s=%s" % (k, v) for (k, v) in sorted(scopes.items()))
        return "\n".join(result)
