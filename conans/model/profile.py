import copy
from collections import OrderedDict
from conans.util.config_parser import ConfigParser
from conans.model.scope import Scopes, _root
from conans.errors import ConanException
from collections import defaultdict


def _clean_value(value):
    '''Strip a value and remove the quotes. EX:
    key="value " => str('value')
    '''
    value = value.strip()
    if value.startswith('"') and value.endswith('"') and value != '"':
        value = value[1:-1]
    if value.startswith("'") and value.endswith("'") and value != "'":
        value = value[1:-1]
    return value


class Profile(object):
    '''A profile contains a set of setting (with values), environment variables
    and scopes'''

    def __init__(self):
        # Sections
        self._settings = OrderedDict()
        self._package_settings = defaultdict(OrderedDict)
        self._env = OrderedDict()
        self._package_env = defaultdict(OrderedDict)
        self.scopes = Scopes()

    @property
    def package_settings(self):
        return {package_name: list(settings.items()) for package_name, settings in self._package_settings.items()}

    @property
    def settings(self):
        return list(self._settings.items())

    @property
    def package_env(self):
        return {package_name: list(env.items()) for package_name, env in self._package_env.items()}

    @property
    def env(self):
        return list(self._env.items())

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
            value = _clean_value(value)
            return package_name, name, value

        try:
            obj = Profile()
            doc = ConfigParser(text, allowed_fields=["settings", "env", "scopes"])

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

            for env in doc.env.splitlines():
                env = env.strip()
                if env and not env.startswith("#"):
                    if "=" not in env:
                        raise ConanException("Invalid env line '%s'" % env)
                    package_name, name, value = get_package_name_value(env)
                    if package_name:
                        obj._package_env[package_name][name] = value
                    else:
                        obj._env[name] = value

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

        result.append("[scopes]")
        if self.scopes[_root].get("dev", None):
            # FIXME: Ugly _root import
            del self.scopes[_root]["dev"]  # Do not include dev
        scopes_txt = self.scopes.dumps()
        result.append(scopes_txt)

        result.append("[env]")
        dump_simple_items(self._env.items(), result)
        dump_package_items(self._package_env.items(), result)

        return "\n".join(result).replace("\n\n", "\n")

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

    def update_env(self, new_env):
        '''Priorize new_env to override the current envs'''
        if not new_env:
            return
        self._env = self._mix_env_with_new(self._env, new_env)

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

        tmp_env = copy.copy(self._env)
        self._env = OrderedDict()
        for ordered_key in sorted(tmp_env):
            self._env[ordered_key] = tmp_env[ordered_key]
