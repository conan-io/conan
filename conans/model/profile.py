import copy
from collections import OrderedDict, defaultdict

from conan.tools.env.environment import ProfileEnvironment
from conans.client import settings_preprocessor
from conans.errors import ConanException
from conans.model.conf import ConfDefinition
from conans.model.options import Options
from conans.model.ref import ConanFileReference
from conans.model.values import Values


class Profile(object):
    """A profile contains a set of setting (with values), environment variables
    """

    def __init__(self):
        # Input sections, as defined by user profile files and command line
        self.settings = OrderedDict()
        self.package_settings = defaultdict(OrderedDict)
        self.options = Options()
        self.build_requires = OrderedDict()  # ref pattern: list of ref
        self.conf = ConfDefinition()
        self.buildenv = ProfileEnvironment()

        # Cached processed values
        self.processed_settings = None  # Settings with values, and smart completion
        self._package_settings_values = None
        self.dev_reference = None  # Reference of the package being develop

    def __repr__(self):
        return self.dumps()

    @property
    def package_settings_values(self):
        if self._package_settings_values is None:
            self._package_settings_values = {}
            for pkg, settings in self.package_settings.items():
                self._package_settings_values[pkg] = list(settings.items())
        return self._package_settings_values

    def process_settings(self, cache):
        assert self.processed_settings is None, "processed settings must be None"
        self.processed_settings = cache.settings.copy()
        self.processed_settings.values = Values.from_list(list(self.settings.items()))

        settings_preprocessor.preprocess(self.processed_settings)
        # Redefine the profile settings values with the preprocessed ones
        # FIXME: Simplify the values.as_list()
        self.settings = OrderedDict(self.processed_settings.values.as_list())
        # Per-package settings cannot be processed here, until composed not possible

    def dumps(self):
        result = ["[settings]"]
        for name, value in self.settings.items():
            result.append("%s=%s" % (name, value))
        for package, values in self.package_settings.items():
            for name, value in values.items():
                result.append("%s:%s=%s" % (package, name, value))

        result.append("[options]")
        result.append(self.options.dumps())

        result.append("[build_requires]")
        for pattern, req_list in self.build_requires.items():
            result.append("%s: %s" % (pattern, ", ".join(str(r) for r in req_list)))

        result.append("[env]")
        result.append("")

        if self.conf:
            result.append("[conf]")
            result.append(self.conf.dumps())

        if self.buildenv:
            result.append("[buildenv]")
            result.append(self.buildenv.dumps())

        return "\n".join(result).replace("\n\n", "\n")

    def compose_profile(self, other):
        self.update_settings(other.settings)
        self.update_package_settings(other.package_settings)
        self.options.update_options(other.options)
        # It is possible that build_requires are repeated, or same package but different versions
        for pattern, req_list in other.build_requires.items():
            existing_build_requires = self.build_requires.get(pattern)
            existing = OrderedDict()
            if existing_build_requires is not None:
                for br in existing_build_requires:
                    # TODO: Understand why sometimes they are str and other are ConanFileReference
                    r = ConanFileReference.loads(br) \
                         if not isinstance(br, ConanFileReference) else br
                    existing[r.name] = br
            for req in req_list:
                r = ConanFileReference.loads(req) \
                     if not isinstance(req, ConanFileReference) else req
                existing[r.name] = req
            self.build_requires[pattern] = list(existing.values())

        self.conf.update_conf_definition(other.conf)
        self.buildenv.update_profile_env(other.buildenv)  # Profile composition, last has priority

    def update_settings(self, new_settings):
        """Mix the specified settings with the current profile.
        Specified settings are prioritized to profile"""

        assert(isinstance(new_settings, OrderedDict))

        # apply the current profile
        res = copy.copy(self.settings)
        if new_settings:
            # Invalidate the current subsettings if the parent setting changes
            # Example: new_settings declare a different "compiler",
            # so invalidate the current "compiler.XXX"
            for name, value in new_settings.items():
                if "." not in name:
                    if name in self.settings and self.settings[name] != value:
                        for cur_name, _ in self.settings.items():
                            if cur_name.startswith("%s." % name):
                                del res[cur_name]
            # Now merge the new values
            res.update(new_settings)
            self.settings = res

    def update_package_settings(self, package_settings):
        """Mix the specified package settings with the specified profile.
        Specified package settings are prioritized to profile"""
        for package_name, settings in package_settings.items():
            self.package_settings[package_name].update(settings)
