import copy
from collections import OrderedDict
from conans.util.config_parser import ConfigParser
from conans.model.scope import Scopes, _root
from conans.errors import ConanException


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
        self.settings = OrderedDict()
        self.env = OrderedDict()
        self.scopes = Scopes()

    @staticmethod
    def loads(text):
        try:
            obj = Profile()
            doc = ConfigParser(text, allowed_fields=["settings", "env", "scopes"])

            for setting in doc.settings.splitlines():
                setting = setting.strip()
                if setting and not setting.startswith("#"):
                    if "=" not in setting:
                        raise ConanException("Invalid setting line '%s'" % setting)
                    name, value = setting.split("=", 1)
                    obj.settings[name.strip()] = _clean_value(value)

            if doc.scopes:
                obj.scopes = Scopes.from_list(doc.scopes.splitlines())

            for env in doc.env.splitlines():
                env = env.strip()
                if env and not env.startswith("#"):
                    if "=" not in env:
                        raise ConanException("Invalid env line '%s'" % env)
                    varname, value = env.split("=", 1)
                    obj.env[varname.strip()] = _clean_value(value)

            obj._order()
            return obj
        except ConanException:
            raise
        except Exception as exc:
            raise ConanException("Error parsing the profile text file: %s" % str(exc))

    def dumps(self):
        self._order()  # gets in order the settings

        result = ["[settings]"]
        for name, value in self.settings.items():
            result.append("%s=%s" % (name, value))

        result.append("[scopes]")
        if self.scopes[_root].get("dev", None):
            # FIXME: Ugly _root import
            del self.scopes[_root]["dev"]  # Do not include dev
        scopes_txt = self.scopes.dumps()
        result.append(scopes_txt)

        result.append("[env]")
        for name, value in self.env.items():
            result.append("%s=%s" % (name, value))

        return "\n".join(result).replace("\n\n", "\n")

    def update_settings(self, new_settings):
        '''Mix the specified settings with the current profile.
        Specified settings are prioritized to profile'''
        # apply the current profile
        if new_settings:
            self.settings.update(new_settings)
            self._order()

    def update_scopes(self, new_scopes):
        '''Mix the specified settings with the current profile.
        Specified settings are prioritized to profile'''
        # apply the current profile
        if new_scopes:
            self.scopes.update(new_scopes)
            self._order()

    def _order(self):
        tmp_settings = copy.copy(self.settings)
        self.settings = OrderedDict()
        # Insert in a good order
        for func in [lambda x: "." not in x,  # First the principal settings
                     lambda x: "." in x]:
            for name, value in tmp_settings.items():
                if func(name):
                    self.settings[name] = value

        tmp_env = copy.copy(self.env)
        self.env = OrderedDict()
        for ordered_key in sorted(tmp_env):
            self.env[ordered_key] = tmp_env[ordered_key]
        