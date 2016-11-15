from conans.errors import ConanException
from conans.paths import conan_expand_user
from conans import tools

import yaml
import os
import sys

class EmbeddedSettingsParser:
    def __init__(self, filename):
        with open(filename, "r") as f:
            self.data = yaml.load(f.read())
        targets = set()
        parents = set()
        for (k, v) in self.data.items():
            targets.add(k)
            if v != None:
                parents = parents.union(set(v))
        if not parents.issubset(targets):
            raise ConanException("[ERROR] Undeclared parents : " + str(parents.difference(targets)))

    def get_microcontroller(self, target):
        target = str(target)
        if not self.data.has_key(target):
            return None
        for t in self.get_groups(target):
            if self.data[t] != None and "mcu" in self.data[t]:
                return t
        return None

    def get_groups(self, target):
        target = str(target)
        if not self.data.has_key(target):
            return set()
        ret = set([target])
        if self.data[target] == None:
            return ret
        for p in self.data[target]:
            ret.add(p)
            ret = ret.union(self.get_groups(p))
        return ret

class Embedded:
    # VERY DIRTY !
    user_folder = os.getenv("CONAN_USER_HOME", conan_expand_user("~"))
    conan_folder = os.path.join(user_folder, ".conan")
    embedded_settings_path = os.path.join(conan_folder, "conan-embedded-settings-master")
    if not os.path.exists(embedded_settings_path):
        tools.download("https://github.com/astralien3000/conan-embedded-settings/archive/master.zip", "embedded-settings.zip")
        tools.unzip("embedded-settings.zip", conan_folder)
    settings = EmbeddedSettingsParser(os.path.join(embedded_settings_path, "test.yml"))

    def __init__(self, settings):
        if not settings.target in Embedded.settings.data.keys():
            raise ConanException("[ERROR] Invalid target : " + str(settings.target))
        self.target = settings.target

    def name(self):
        return self.target

    def microcontroller(self):
        return Embedded.settings.get_microcontroller(self.target)

    def groups(self):
        return Embedded.settings.get_groups(self.target)
