from collections import defaultdict
from conans.errors import ConanException


class Scope(set):
    def __getattr__(self, field):
        if field in self:
            return True
        return False


class Scopes(defaultdict):
    def __init__(self):
        super(Scopes, self).__init__(Scope)
        self[None].add("dev")

    @staticmethod
    def from_list(items):
        result = Scopes()
        for item in items:
            chunks = item.split(":")
            if len(chunks) == 2:
                result[chunks[0]].add(chunks[1])
            elif len(chunks) == 1:
                result[None].add(item)
            else:
                raise ConanException("Bad scope %s" % item)
        if "!dev" in result[None]:
            result[None].remove("!dev")
            result[None].remove("dev")
        return result

    @staticmethod
    def loads(text):
        return Scopes.from_list([s.strip() for s in text.splitlines()])

    def dumps(self):
        result = []
        for name, scopes in self.items():
            if name:
                result.extend("%s:%s" % (name, s) for s in sorted(scopes))
            else:
                result.extend(sorted(scopes))
        return "\n".join(result)
