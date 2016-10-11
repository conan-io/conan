from conans.util.config_parser import ConfigParser
import copy
from collections import OrderedDict


class Profile(object):
    '''A profile contains a set of setting (with values) and compiler paths'''

    def __init__(self):
        # Sections
        self.settings = OrderedDict()
        # NOT SURE ABOUT COMPILERS, ENV VARS? self.compilers = {}

    @staticmethod
    def loads(text):
        obj = Profile()
        doc = ConfigParser(text, allowed_fields=["settings", "compilers"])
        for setting in doc.settings.split("\n"):
            if setting:
                name, value = setting.split("=")
                obj.settings[name] = value
        obj._order()
        return obj

    def dumps(self):
        result = ["[settings]"]
        self._order()  # gets in order
        for name, value in self.settings.items():
            result.append("%s=%s" % (name, value))

        return "\n".join(result)

    def update_settings(self, new_settings):
        '''Mix the specified settings with the current profile.
        Specified settings are prioritized to profile'''
        # apply the current profile
        self.settings.update(new_settings)
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
