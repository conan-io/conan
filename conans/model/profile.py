from collections import OrderedDict
from collections import defaultdict

from conans.model.env_info import EnvValues
from conans.model.options import OptionsValues
from conans.model.scope import Scopes, _root
from conans.model.values import Values


class Profile(object):
    """A profile contains a set of setting (with values), environment variables
    and scopes"""

    def __init__(self):
        # Sections
        self.settings = OrderedDict()
        self.package_settings = defaultdict(OrderedDict)
        self.env_values = EnvValues()
        self.scopes = Scopes()
        self.options = OptionsValues()
        self.build_requires = OrderedDict()  # conan_ref Pattern: list of conan_ref

    @property
    def settings_values(self):
        return Values.from_list(list(self.settings.items()))

    @property
    def package_settings_values(self):
        result = {}
        for pkg, settings in self.package_settings.items():
            result[pkg] = list(settings.items())
        return result

    def dumps(self):
        result = ["[build_requires]"]
        for pattern, req_list in self.build_requires.items():
            result.append("%s: %s" % (pattern, ", ".join(str(r) for r in req_list)))
        result.append("[settings]")
        for name, value in self.settings.items():
            result.append("%s=%s" % (name, value))
        for package, values in self.package_settings.items():
            for name, value in values.items():
                result.append("%s:%s=%s" % (package, name, value))

        result.append("[options]")
        result.append(self.options.dumps())

        result.append("[scopes]")
        if self.scopes[_root].get("dev", None):
            # FIXME: Ugly _root import
            del self.scopes[_root]["dev"]  # Do not include dev
        scopes_txt = self.scopes.dumps()
        result.append(scopes_txt)

        result.append("[env]")
        result.append(self.env_values.dumps())

        return "\n".join(result).replace("\n\n", "\n")

    def update(self, other):
        self.update_settings(other.settings)
        self.update_package_settings(other.package_settings)
        self.update_scopes(other.scopes)
        # this is the opposite
        other.env_values.update(self.env_values)
        self.env_values = other.env_values
        self.options.update(other.options)
        for pattern, req_list in other.build_requires.items():
            self.build_requires.setdefault(pattern, []).extend(req_list)

    def update_settings(self, new_settings):
        '''Mix the specified settings with the current profile.
        Specified settings are prioritized to profile'''
        # apply the current profile
        if new_settings:
            self.settings.update(new_settings)

    def update_package_settings(self, package_settings):
        '''Mix the specified package settings with the specified profile.
        Specified package settings are prioritized to profile'''
        for package_name, settings in package_settings.items():
            self.package_settings[package_name].update(settings)

    def update_scopes(self, new_scopes):
        '''Mix the specified settings with the current profile.
        Specified settings are prioritized to profile'''
        # apply the current profile
        if new_scopes:
            self.scopes.update(new_scopes)
