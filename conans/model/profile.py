import copy
from collections import OrderedDict, defaultdict

from conans.client import settings_preprocessor
from conans.errors import ConanException
from conans.model.env_info import EnvValues
from conans.model.options import OptionsValues
from conans.model.values import Values


class _ProfileSettings(object):
    def __init__(self):
        self.processed_settings = None
        self.settings = OrderedDict()

    def process_settings(self, cache, preprocess=True):
        self.processed_settings = cache.settings.copy()
        self.processed_settings.values = Values.from_list(list(self.settings.items()))
        if preprocess:
            settings_preprocessor.preprocess(self.processed_settings)
            # Redefine the profile settings values with the preprocessed ones
            # FIXME: Simplify the values.as_list()
            self.settings = OrderedDict(self.processed_settings.values.as_list())

    def _dumps(self, pkg_name):
        scope_str = "{}:".format(pkg_name) if pkg_name else ""
        result = []
        for name, value in self.settings.items():
            result.append("%s%s=%s" % (scope_str, name, value))
        return "\n".join(result).replace("\n\n", "\n")

    def update(self, other):
        # Specified settings are prioritized to profile
        self.update_settings(other.settings)

    def update_settings(self, new_settings):
        """Mix the specified settings with the current profile.
        Specified settings are prioritized to profile"""

        assert(isinstance(new_settings, OrderedDict)), "Type: {}".format(type(new_settings))

        # apply the current profile
        res = copy.copy(self.settings)
        if new_settings:
            # Invalidate the current subsettings if the parent setting changes
            # Example: new_settings declare a different "compiler", so invalidate the
            #  current "compiler.XXX"
            for name, value in new_settings.items():
                if "." not in name:
                    if name in self.settings and self.settings[name] != value:
                        for cur_name, _ in self.settings.items():
                            if cur_name.startswith("%s." % name):
                                del res[cur_name]
            # Now merge the new values
            res.update(new_settings)
            self.settings = res


PackageSettings = _ProfileSettings


class Profile(_ProfileSettings):
    """A profile contains a set of setting (with values), environment variables
    """

    def __init__(self):
        # Sections
        super(Profile, self).__init__()
        self._package_settings = defaultdict(PackageSettings)
        self.env_values = EnvValues()
        self.options = OptionsValues()
        self.build_requires = OrderedDict()

    def package_settings(self, package_name):
        return self._package_settings[package_name]

    def process_settings(self, cache, preprocess=True):
        super(Profile, self).process_settings(cache, preprocess)

        for package_name, settings in self._package_settings.items():
            try:
                settings.process_settings(cache, preprocess=preprocess)
            except ConanException as e:
                raise ConanException("[{}] {}".format(package_name, e))

    def dumps(self):
        result = ["[settings]", ]
        result.append(self._dumps(None))
        for package, values in self._package_settings.items():
            result.append(values._dumps(package))

        result.append("[options]")
        result.append(self.options.dumps())

        result.append("[build_requires]")
        for pattern, req_list in self.build_requires.items():
            result.append("%s: %s" % (pattern, ", ".join(str(r) for r in req_list)))

        result.append("[env]")
        result.append(self.env_values.dumps())

        return "\n".join(result).replace("\n\n", "\n")

    def update(self, other):
        # Specified settings are prioritized to profile
        super(Profile, self).update(other)
        for name, package_settings in other._package_settings.items():
            self.update_package_settings(name, package_settings.settings)

        # this is the opposite
        other.env_values.update(self.env_values)
        self.env_values = other.env_values
        self.options.update(other.options)
        for pattern, req_list in other.build_requires.items():
            self.build_requires.setdefault(pattern, []).extend(req_list)

    def update_package_settings(self, name, settings):
        """Mix the specified package settings with the specified profile.
        Specified package settings are prioritized to profile"""
        self._package_settings.setdefault(name, PackageSettings()).update_settings(settings)
