import copy
from collections import OrderedDict
from conans.util.config_parser import ConfigParser
from conans.model.scope import Scopes


class Profile(object):
    '''A profile contains a set of setting (with values), environment variables
    and scopes'''

    def __init__(self):
        # Sections
        self.settings = OrderedDict()
        self.env = dict()
        self.scopes = Scopes()

    @staticmethod
    def loads(text):
        obj = Profile()
        doc = ConfigParser(text, allowed_fields=["settings", "env", "scopes"])

        for setting in doc.settings.split("\n"):
            if setting:
                name, value = setting.split("=")
                obj.settings[name] = value

        if doc.scopes:
            obj.scopes = Scopes.from_list(doc.scopes.split("\n"))

        for env in doc.env.split("\n"):
            if env:
                varname, value = env.split("=")
                obj.env[varname] = value

        obj._order()
        return obj

    def dumps(self):
        self._order()  # gets in order

        result = ["[settings]"]
        for name, value in self.settings.items():
            result.append("%s=%s" % (name, value))

        result.append("[scopes]")
        scopes = self.scopes.dumps()
        # FIXME: Don't want the root scope dev in the profile, but this replace is ugly
        result.append(scopes.replace("dev=True\n", "").replace("dev=True", ""))

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
