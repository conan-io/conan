import copy
from collections import OrderedDict, defaultdict

from conans.client import settings_preprocessor
from conans.errors import ConanException
from conans.model.env_info import EnvValues
from conans.model.options import OptionsValues
from conans.model.values import Values


class Config(object):
    def __init__(self):
        self._components = {}  # Component => dict {config-name: value}

    def __bool__(self):
        return bool(self._components)

    def __getitem__(self, item):
        return self._components[item]

    def __repr__(self):
        return "Config: " + repr(self._components)

    __nonzero__ = __bool__

    def update(self, other):
        self._components.update(other._components)

    def dumps(self):
        result = []
        for name, values in self._components.items():
            for k, v in values.items():
                result.append("{}:{}={}".format(name, k, v))
        return "\n".join(result)

    def loads(self, text):
        self._components = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            left, value = line.split("=", 1)
            component, name = left.split(":", 1)
            self._components.setdefault(component, {})[name] = value
        print(self)


class Profile(object):
    """A profile contains a set of setting (with values), environment variables
    """

    def __init__(self):
        # Input sections, as defined by user profile files and command line
        self.settings = OrderedDict()
        self.package_settings = defaultdict(OrderedDict)
        self.env_values = EnvValues()
        self.options = OptionsValues()
        self.build_requires = OrderedDict()  # ref pattern: list of ref
        self.config = Config()

        # Cached processed values
        self.processed_settings = None  # Settings with values, and smart completion
        self._user_options = None
        self._package_settings_values = None
        self.dev_reference = None  # Reference of the package being develop

    @property
    def user_options(self):
        if self._user_options is None:
            self._user_options = self.options.copy()
        return self._user_options

    @property
    def package_settings_values(self):
        if self._package_settings_values is None:
            self._package_settings_values = {}
            for pkg, settings in self.package_settings.items():
                self._package_settings_values[pkg] = list(settings.items())
        return self._package_settings_values

    def process_settings(self, cache, preprocess=True):
        assert self.processed_settings is None, "processed settings must be None"
        self.processed_settings = cache.settings.copy()
        self.processed_settings.values = Values.from_list(list(self.settings.items()))
        if preprocess:
            settings_preprocessor.preprocess(self.processed_settings)
            # Redefine the profile settings values with the preprocessed ones
            # FIXME: Simplify the values.as_list()
            self.settings = OrderedDict(self.processed_settings.values.as_list())

            # Preprocess also scoped settings
            for pkg, pkg_settings in self.package_settings.items():
                pkg_profile = Profile()
                pkg_profile.settings = self.settings
                pkg_profile.update_settings(pkg_settings)
                try:
                    pkg_profile.process_settings(cache=cache, preprocess=True)
                except Exception as e:
                    pkg_profile = ["{}={}".format(k, v) for k, v in pkg_profile.settings.items()]
                    raise ConanException("Error in resulting settings for package"
                                         " '{}': {}\n{}".format(pkg, e, '\n'.join(pkg_profile)))
                # TODO: Assign the _validated_ settings and do not compute again

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
        result.append(self.env_values.dumps())

        if self.config:
            result.append("[config]")
            result.append(self.config.dumps())

        return "\n".join(result).replace("\n\n", "\n")

    def update(self, other):
        self.update_settings(other.settings)
        self.update_package_settings(other.package_settings)
        # this is the opposite
        other.env_values.update(self.env_values)
        self.env_values = other.env_values
        self.options.update(other.options)
        for pattern, req_list in other.build_requires.items():
            self.build_requires.setdefault(pattern, []).extend(req_list)
        self.config.update(other.config)

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
