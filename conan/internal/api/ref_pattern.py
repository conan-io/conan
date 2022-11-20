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
        self.pid, prev = split(package, "#", prev)
        self.prev, _ = split(prev, "%")
