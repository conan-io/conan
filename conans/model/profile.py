from collections import OrderedDict
from conans.util.config_parser import ConfigParser
from conans.model.scope import Scopes, _root
from conans.errors import ConanException
from collections import defaultdict
from conans.model.env_info import EnvValues, unquote
from conans.model.options import OptionsValues
import os
from conans.util.files import load, mkdir
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

    @property
    def settings_values(self):
        return Values.from_list(list(self.settings.items()))

    @property
    def package_settings_values(self):
        result = {}
        for pkg, settings in self.package_settings.items():
            result[pkg] = list(settings.items())
        return result

    @staticmethod
    def read_file(profile_name, cwd, default_folder):
        """ Will look for "profile_name" in disk if profile_name is absolute path,
        in current folder if path is relative or in the default folder otherwise.
        return: a Profile object
        """
        if not profile_name:
            return None

        if os.path.isabs(profile_name):
            profile_path = profile_name
            folder = os.path.dirname(profile_name)
        elif profile_name.startswith("."):  # relative path name
            profile_path = os.path.abspath(os.path.join(cwd, profile_name))
            folder = os.path.dirname(profile_path)
        else:
            folder = default_folder
            if not os.path.exists(folder):
                mkdir(folder)
            profile_path = os.path.join(folder, profile_name)

        try:
            text = load(profile_path)
        except IOError:
            if os.path.exists(folder):
                profiles = [name for name in os.listdir(folder) if not os.path.isdir(name)]
            else:
                profiles = []
            current_profiles = ", ".join(profiles) or "[]"
            raise ConanException("Specified profile '%s' doesn't exist.\nExisting profiles: "
                                 "%s" % (profile_name, current_profiles))

        try:
            text = text.replace("$PROFILE_DIR", os.path.abspath(folder))  # Allows PYTHONPATH=$PROFILE_DIR/pythontools
            return Profile.loads(text)
        except ConanException as exc:
            raise ConanException("Error reading '%s' profile: %s" % (profile_name, exc))

    @staticmethod
    def loads(text):
        """ Parse and return a Profile object from a text config like representation
        """
        def get_package_name_value(item):
            '''Parse items like package:name=value or name=value'''
            package_name = None
            if ":" in item:
                tmp = item.split(":", 1)
                package_name, item = tmp

            name, value = item.split("=", 1)
            name = name.strip()
            value = unquote(value)
            return package_name, name, value

        try:
            obj = Profile()
            doc = ConfigParser(text, allowed_fields=["settings", "env", "scopes", "options"])

            for setting in doc.settings.splitlines():
                setting = setting.strip()
                if setting and not setting.startswith("#"):
                    if "=" not in setting:
                        raise ConanException("Invalid setting line '%s'" % setting)
                    package_name, name, value = get_package_name_value(setting)
                    if package_name:
                        obj.package_settings[package_name][name] = value
                    else:
                        obj.settings[name] = value

            if doc.scopes:
                obj.scopes = Scopes.from_list(doc.scopes.splitlines())

            if doc.options:
                obj.options = OptionsValues.loads(doc.options)

            obj.env_values = EnvValues.loads(doc.env)

            return obj
        except ConanException:
            raise
        except Exception as exc:
            raise ConanException("Error parsing the profile text file: %s" % str(exc))

    def dumps(self):
        result = ["[settings]"]
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
