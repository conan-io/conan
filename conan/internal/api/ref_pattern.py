class RefPattern:
    def __init__(self, expression, rrev=None, prev=None):

        def split(s, c, default=None):
            if not s:
                return None, default
            tokens = s.split(c, 1)
            if len(tokens) == 2:
                return tokens
            return tokens[0], default

        recipe, package = split(expression, ":")
        self.ref, self.rrev = split(recipe, "#", rrev)
        self.pid, self.prev = split(package, "#", prev)
