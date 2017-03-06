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


def initialize_profile(settings, current_path=None, profile=None):
    conaninfo_scopes = Scopes()
    user_options = user_options_values or OptionsValues()
    mixed_env_values = EnvValues()
    mixed_env_values.update(env_values)

    if current_path:
        conan_info_path = os.path.join(current_path, CONANINFO)
        if use_conaninfo and os.path.exists(conan_info_path):
            existing_info = ConanInfo.load_file(conan_info_path)
            settings.values = existing_info.full_settings
            options = existing_info.full_options  # Take existing options from conaninfo.txt
            options.update(user_options)
            user_options = options
            conaninfo_scopes = existing_info.scope
            # Update with info (prioritize user input)
            mixed_env_values.update(existing_info.env_values)

    if user_settings_values:
        aux_values = Values.from_list(user_settings_values)
        settings.values = aux_values

    if scopes:
        conaninfo_scopes.update_scope(scopes)
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
        self._settings = OrderedDict()
        self._package_settings = defaultdict(OrderedDict)
        self.env_values = EnvValues()
        self.scopes = Scopes()
        self.options = OptionsValues()

    @property
    def package_settings(self):
        return {package_name: list(settings.items()) for package_name, settings in self._package_settings.items()}

    @property
    def settings(self):
        return list(self._settings.items())

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
                        obj._package_settings[package_name][name] = value
                    else:
                        obj._settings[name] = value

            if doc.scopes:
                obj.scopes = Scopes.from_list(doc.scopes.splitlines())

            if doc.options:
                obj.options = OptionsValues.loads(doc.options)

            obj.env_values = EnvValues.loads(doc.env)
            obj._order()
            return obj
        except ConanException:
            raise
        except Exception as exc:
            raise ConanException("Error parsing the profile text file: %s" % str(exc))

    def dumps(self):
        self._order()  # gets in order the settings

        def dump_simple_items(items, result):
            for name, value in items:
                result.append("%s=%s" % (name, value))

        def dump_package_items(items, result):
            for package, values in items:
                for name, value in values.items():
                    result.append("%s:%s=%s" % (package, name, value))

        result = ["[settings]"]
        dump_simple_items(self._settings.items(), result)
        dump_package_items(self._package_settings.items(), result)

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
        self.update_settings(other._settings)
        self.update_package_settings(other._package_settings)
        # Scopes
        self.update_scopes(other.scopes)
        other.env_values.update(self.env_values)
        self.options.update(other.options)
        
    def update_settings(self, new_settings):
        '''Mix the specified settings with the current profile.
        Specified settings are prioritized to profile'''
        # apply the current profile
        if new_settings:
            self._settings.update(new_settings)
            self._order()

    def update_package_settings(self, package_settings):
        '''Mix the specified package settings with the specified profile.
        Specified package settings are prioritized to profile'''
        for package_name, settings in self._package_settings.items():
            if package_name in package_settings:
                settings.update(dict(package_settings[package_name]))

        # The rest of new packages settings
        for package_name, settings in package_settings.items():
            if package_name not in self._package_settings:
                self._package_settings[package_name].update(dict(settings))

        self._order()

    def _mix_env_with_new(self, env_dict, new_env):

        res_env = OrderedDict()
        for name, value in new_env:
            if name in env_dict:
                del env_dict[name]
            res_env[name] = value  # Insert first in the result

        for name, value in env_dict.items():
            res_env[name] = value  # Insert the rest of env vars at the end

        return res_env

    def update_packages_env(self, new_packages_env):
        '''Priorize new_packages_env to override the current package_env'''
        if not new_packages_env:
            return
        res_env = defaultdict(OrderedDict)

        # Mix the common packages env
        for package, env_vars in self._package_env.items():
            new_env = new_packages_env.get(package, [])
            res_env[package] = self._mix_env_with_new(env_vars, new_env)

        # The rest of new packages env variables
        for package, env_vars in new_packages_env.items():
            if package not in res_env:
                for name, value in env_vars:
                    res_env[package][name] = value  # Insert the rest of env vars at the end

        self._package_env = res_env

    def update_scopes(self, new_scopes):
        '''Mix the specified settings with the current profile.
        Specified settings are prioritized to profile'''
        # apply the current profile
        if new_scopes:
            self.scopes.update(new_scopes)
            self._order()

    def _order(self):

        def order_single_settings(settings):
            ret = OrderedDict()
            # Insert in a good order
            for func in [lambda x: "." not in x,  # First the principal settings
                         lambda x: "." in x]:
                for name, value in settings.items():
                    if func(name):
                        ret[name] = value
            return ret

        # Order global settings
        self._settings = order_single_settings(self._settings)

        # Order package settings
        for package_name, settings in self._package_settings.items():
            self._package_settings[package_name] = order_single_settings(settings)
