from collections import OrderedDict
from conans.util.config_parser import ConfigParser
from conans.model.scope import Scopes, _root
from conans.errors import ConanException
from collections import defaultdict
from conans.model.env_info import EnvValues, unquote
from conans.model.options import OptionsValues
import os
from conans.util.files import load, mkdir
from conans.paths import CONANINFO
from conans.model.info import ConanInfo
from conans.model.values import Values


def initialize_profile(settings, current_path=None, profile=None):
    result = Profile()

    if profile is None:
        if current_path:
            conan_info_path = os.path.join(current_path, CONANINFO)
            if os.path.exists(conan_info_path):
                existing_info = ConanInfo.load_file(conan_info_path)
                settings.values = existing_info.full_settings
                result.options = existing_info.full_options
                result.scopes = existing_info.scope
                result.env_values = existing_info.env_values
    else:
        result.env_values.update(profile.env_values)
        settings.values = profile.settings_values
        if profile.scopes:
            result.scopes.update_scope(profile.scopes)
        result.options.update(profile.options)
        for pkg, settings in profile.package_settings.items():
            result.package_settings[pkg].update(settings)
    return result


def read_profile_args(args, cwd, default_folder):
    file_profile = read_profile_file(args.profile, cwd, default_folder)
    args_profile = Profile.parse(args.settings, args.options, args.env, args.scope)

    if file_profile:
        # Settings
        file_profile.update(args_profile)
        return file_profile
    else:
        return args_profile


def read_profile_file(profile_name, cwd, default_folder):
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
    except Exception:
        if os.path.exists(folder):
            profiles = [name for name in os.listdir(folder) if not os.path.isdir(name)]
        else:
            profiles = []
        current_profiles = ", ".join(profiles) or "[]"
        raise ConanException("Specified profile '%s' doesn't exist.\nExisting profiles: "
                             "%s" % (profile_name, current_profiles))

    try:
        return Profile.loads(text)
    except ConanException as exc:
        raise ConanException("Error reading '%s' profile: %s" % (profile_name, exc))


class Profile(object):
    '''A profile contains a set of setting (with values), environment variables
    and scopes'''

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
    def parse(settings, options, envs, scopes):
        def _get_tuples_list_from_extender_arg(items):
            if not items:
                return []
            # Validate the pairs
            for item in items:
                chunks = item.split("=")
                if len(chunks) != 2:
                    raise ConanException("Invalid input '%s', use 'name=value'" % item)
            return [(item[0], item[1]) for item in [item.split("=") for item in items]]

        def _get_simple_and_package_tuples(items):
            """Parse items like "thing:item=value or item2=value2 and returns a tuple list for
            the simple items (name, value) and a dict for the package items
            {package: [(item, value)...)], ...}
            """
            simple_items = []
            package_items = defaultdict(list)
            tuples = _get_tuples_list_from_extender_arg(items)
            for name, value in tuples:
                if ":" in name:  # Scoped items
                    tmp = name.split(":", 1)
                    ref_name = tmp[0]
                    name = tmp[1]
                    package_items[ref_name].append((name, value))
                else:
                    simple_items.append((name, value))
            return simple_items, package_items

        def _get_env_values(env, package_env):
            env_values = EnvValues()
            for name, value in env:
                env_values.add(name, EnvValues.load_value(value))
            for package, data in package_env.items():
                for name, value in data:
                    env_values.add(name, EnvValues.load_value(value), package)
            return env_values

        result = Profile()
        options = _get_tuples_list_from_extender_arg(options)
        result.options = OptionsValues(options)
        env, package_env = _get_simple_and_package_tuples(envs)
        env_values = _get_env_values(env, package_env)
        result.env_values = env_values
        settings, package_settings = _get_simple_and_package_tuples(settings)
        result.settings = OrderedDict(settings)
        for pkg, values in package_settings.items():
            result.package_settings[pkg] = OrderedDict(values)
        result.scopes = Scopes.from_list(scopes) if scopes else None
        return result

    @staticmethod
    def loads(text):
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

    def _mix_env_with_new(self, env_dict, new_env):
        res_env = OrderedDict()
        for name, value in new_env:
            if name in env_dict:
                del env_dict[name]
            res_env[name] = value  # Insert first in the result

        for name, value in env_dict.items():
            res_env[name] = value  # Insert the rest of env vars at the end

        return res_env

    def update_scopes(self, new_scopes):
        '''Mix the specified settings with the current profile.
        Specified settings are prioritized to profile'''
        # apply the current profile
        if new_scopes:
            self.scopes.update(new_scopes)
