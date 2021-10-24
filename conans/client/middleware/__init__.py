import fnmatch
import os

from conans.client.recorder.action_recorder import ActionRecorder
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirement


class MiddlewareLoader(object):
    def __init__(self, proxy, range_resolver):
        self._proxy = proxy
        self._range_resolver = range_resolver
        self._cached_modules = {}

    def enable_remotes(self, check_updates=False, update=False, remotes=None):
        self._check_updates = check_updates
        self._update = update
        self._remotes = remotes

    def resolve_middleware_requires(self, loader, conanfile, profile, user, channel, consumer=True):
        ref = ConanFileReference(conanfile.name, conanfile.version, user, channel, validate=False)
        ref_str = str(ref)
        recipe_middleware_requires = []
        for pattern, refs in profile.middleware_requires.items():
            consumer = False
            if ((consumer and pattern == "&") or
                    (not consumer and pattern == "&!") or
                    fnmatch.fnmatch(ref_str, pattern)):
                for ref in refs:
                    if ref not in recipe_middleware_requires:
                        recipe_middleware_requires.append(ref)
        self._resolve_middleware_requires(recipe_middleware_requires, loader)
        return recipe_middleware_requires

    def _resolve_middleware_requires(self, middleware_refs, loader):
        for ref in middleware_refs:
            ref_str = str(ref)
            if ref_str not in self._cached_modules:
                self._cached_modules[ref_str] = self._load_middleware_conanfile(loader, ref)

    def _load_middleware_conanfile(self, loader, ref):
        requirement = Requirement(ref)
        self._range_resolver.resolve(requirement, "middleware", update=self._update,
                                     remotes=self._remotes)
        new_ref = requirement.ref
        recipe = self._proxy.get_recipe(new_ref, self._check_updates, self._update,
                                        remotes=self._remotes, recorder=ActionRecorder())
        path, _, _, new_ref = recipe
        middleware, module = loader.load_middleware(path)
        middleware.name = new_ref.name
        # FIXME Conan 2.0 version should be a string, not a Version object
        middleware.version = new_ref.version

        if getattr(middleware, "alias", None):
            ref = ConanFileReference.loads(middleware.alias)
            requirement = Requirement(ref)
            alias = requirement.alias
            if alias is not None:
                ref = alias
            return self._load_middleware_conanfile(loader, ref)
        return middleware, module, new_ref, os.path.dirname(path)


class MiddlewareManager(object):
    def __init__(self, proxy, range_resolver):
        self._loader = MiddlewareLoader(proxy, range_resolver)
        # Future built-in middleware go here.
        self._middleware = {}

    def enable_remotes(self, *args, **kwargs):
        self._loader.enable_remotes(*args, **kwargs)

    def add(self, name, middleware_class, custom=False):
        if name not in self._middleware or custom:
            self._middleware[name] = middleware_class

    def __contains__(self, name):
        return name in self._middleware

    def __getitem__(self, key):
        return self._middleware[key]

    @staticmethod
    def _initialize_middleware(middleware, profile):
        # Prepare the settings for the loaded middleware
        # Mixing the global settings with the specified for that name if exist
        tmp_settings = profile.processed_settings.copy()
        package_settings_values = profile.package_settings_values
        ref = ConanFileReference(middleware.name or middleware.__class__.__name__,
                                 middleware.version or "1.0",
                                 user=None, channel=None, validate=False)
        ref_str = str(ref)
        if package_settings_values:
            # First, try to get a match directly by name (without needing *)
            # TODO: Conan 2.0: We probably want to remove this, and leave a pure fnmatch
            pkg_settings = package_settings_values.get(middleware.name)

            if middleware.develop and "&" in package_settings_values:
                # "&" overrides the "name" scoped settings.
                pkg_settings = package_settings_values.get("&")

            if pkg_settings is None:  # If there is not exact match by package name, do fnmatch
                for pattern, settings in package_settings_values.items():
                    if fnmatch.fnmatchcase(ref_str, pattern):
                        pkg_settings = settings
                        break
            if pkg_settings:
                tmp_settings.update_values(pkg_settings)

        middleware.initialize(tmp_settings, profile.env_values, profile.buildenv)
        middleware.conf = profile.conf.get_conanfile_conf(ref_str)

    def find_middleware(self, middleware_name):
        try:
            return self._middleware[middleware_name]
        except KeyError:
            available = list(self._middleware.keys())
            raise ConanException("Invalid middleware '%s'. Available types: %s" %
                                 (middleware_name, ", ".join(available)))

    def new_middleware(self, middleware_name, profile, loader):
        cache = profile.cached_middleware
        if middleware_name in cache.middleware:
            return cache.middleware[middleware_name]
        middleware_class = self.find_middleware(middleware_name)
        middleware = middleware_class(loader._output, middleware_name)
        middleware.output.scope = middleware.display_name
        self._initialize_middleware(middleware, profile)
        cache.middleware[middleware_name] = middleware
        return middleware

    def _apply_middleware(self, middleware, conanfile_path, conanfile, user, channel, profile, loader):
        result = conanfile
        applied = []
        for mw in middleware:
            if mw.should_apply(result):
                result = mw(result)
                applied.append(mw)
        if applied:
            # This might be useful if multiple middleware needs to work together?
            result._middleware = applied
        return result

    def apply_middleware(self, conanfile_path, conanfile, user, channel, consumer, profile, loader):
        if not profile:
            return conanfile
        if not profile.middleware:
            return conanfile
        # Don't re-apply middleware
        if hasattr(conanfile, "_middleware"):
            return conanfile
        if conanfile_path in profile.cached_middleware:
            return profile.cached_middleware[conanfile_path]
        # Load middleware_requires first
        self._loader.resolve_middleware_requires(loader, conanfile, profile, user, channel, consumer)
        # Find middleware by conanfile and profile, then instantiate with profile settings
        middleware = self.get_recipe_middleware(conanfile, profile, user, channel, consumer)
        middleware = [self.new_middleware(mw, profile, loader) for mw in middleware]
        # Subclass conanfile
        result = self._apply_middleware(middleware, conanfile_path, conanfile,
                                        user, channel, profile, loader)
        profile.cached_middleware[conanfile_path] = result
        return result

    def get_recipe_middleware(self, conanfile, profile, user, channel, consumer=True):
        ref = ConanFileReference(conanfile.name, conanfile.version, user, channel, validate=False)
        ref_str = str(ref)
        recipe_middleware = []
        for pattern, middleware in profile.middleware.items():
            consumer = False
            if ((consumer and pattern == "&") or
                    (not consumer and pattern == "&!") or
                    fnmatch.fnmatch(ref_str, pattern)):
                for mw in middleware:
                    if mw not in recipe_middleware:
                        recipe_middleware.append(mw)
        return recipe_middleware
