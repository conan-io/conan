class MiddlewareCache(object):
    def __init__(self):
        # Cached middleware instances with profile settings
        self._middleware = {}
        # Recipes wrapped with middleware
        self._recipes = {}

    def __contains__(self, path):
        return path in self._recipes

    def __getitem__(self, path):
        return self._recipes[path]

    def __setitem__(self, path, recipe):
        self._recipes[path] = recipe

    @property
    def middleware(self):
        return self._middleware
