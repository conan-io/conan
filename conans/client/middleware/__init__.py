from conans.client.loader import parse_conanfile
from conans.client.recorder.action_recorder import ActionRecorder
from conans.errors import ConanException
from conans.model.conan_middleware import Middleware
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirement

class MiddlewareManager(object):
    def __init__(self):
        self._middleware = {}
        self._enabled = []

    def add(self, name, middleware_class, custom=False, enable=False):
        if name not in self._middleware or custom:
            self._middleware[name] = middleware_class
            if enable:
                self._enabled.append(middleware_class)

    def __contains__(self, name):
        return name in self._middleware

    def __getitem__(self, key):
        return self._middleware[key]

    def enable_middleware(self, names, loader):
        for name in names:
            if "/" not in name:
                # Look for cached middleware
                try:
                    middleware = self._middleware[name]
                except KeyError:
                    raise ConanException("'%s' is not a middleware" % name)
                self._enabled.append(middleware)

    def get_middleware(self):
        return self._enabled

    def apply_middleware(self, conanfile, profile_host, profile_build):
        result = conanfile
        # Don't re-apply middleware
        if isinstance(conanfile, Middleware):
            return result
        profile = profile_host or profile_build
        for middleware in self.get_middleware():
            wrapped = middleware(result)
            wrapped.initialize(profile.processed_settings.copy())
            if wrapped.valid():
                result = wrapped
        return result
