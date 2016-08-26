from conans.errors import ConanException
from conans.paths import conan_expand_user
from conans.client.paths import ConanPaths
from conans.client.output import ConanOutput
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
                if v.has_key("parents"):
                    parents = parents.union(set(v["parents"]))
                if v.has_key("mcu"):
                    parents.add(v["mcu"])
        if not parents.issubset(targets):
            raise ConanException("[ERROR] Undeclared parents : " + str(parents.difference(targets)))

    def get_microcontroller(self, target):
        target = str(target)
        if not self.data.has_key(target):
            return None
        if not self.data[target].has_key("type"):
            return None
        if self.data[target]["type"] == "mcu":
            return target
        if self.data[target]["type"] == "board":
            return self.data[target]["mcu"]
        return None

    def get_groups(self, target):
        target = str(target)
        if not self.data.has_key(target):
            return set()
        if self.data[target] == None:
            return set()
        ret = set()
        if self.data[target].has_key("parents"):
            for p in self.data[target]["parents"]:
                ret.add(p)
                ret = ret.union(self.get_groups(p))
        if self.data[target].has_key("mcu"):
            ret.add(self.data[target]["mcu"])
            ret = ret.union(self.get_groups(self.data[target]["mcu"]))
        return ret

class Embedded:
    # VERY DIRTY !
    user_folder = os.getenv("CONAN_USER_HOME", conan_expand_user("~"))
    out = ConanOutput(sys.stdout, True)
    paths = ConanPaths(user_folder, None, out)
    if not os.path.exists(paths.embedded_settings_path):
        tools.download("https://github.com/astralien3000/conan-embedded-settings/archive/master.zip", "embedded-settings.zip")
        tools.unzip("embedded-settings.zip", paths.conan_folder)
    settings = EmbeddedSettingsParser(os.path.join(paths.embedded_settings_path, "test.yml"))

    def __init__(self, settings):
        self.target = None
        if settings.target == "mcu":
            self.target = settings.target.mcu
        elif settings.target == "board":
            self.target = settings.target.board
        else:
            raise ConanException("[ERROR] Invalid target : " + str(settings.target))

    def name(self):
        return self.target

    def microcontroller(self):
        return Embedded.settings.get_microcontroller(self.target)

    def groups(self):
        return Embedded.settings.get_groups(self.target)
