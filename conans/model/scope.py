

class Scope(set):
    def __getattr__(self, field):
        if field in self:
            return True
        return False
