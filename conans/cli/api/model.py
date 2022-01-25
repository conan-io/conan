from collections import defaultdict
from typing import List


class Remote:

    def __init__(self, name, url, verify_ssl=True, disabled=False):
        self._name = name  # Read only, is the key
        self.url = url
        self.verify_ssl = verify_ssl
        self.disabled = disabled

    @property
    def name(self):
        return self._name

    def __eq__(self, other):
        if other is None:
            return False
        return self.name == other.name and \
               self.url == other.url and \
               self.verify_ssl == other.verify_ssl and \
               self.disabled == other.disabled

    def __str__(self):
        return "{}: {} [Verify SSL: {}, Enabled: {}]".format(self.name, self.url, self.verify_ssl,
                                                             not self.disabled)


class PkgConfiguration:

    def __init__(self, data):
        self.settings = data.get("settings", {})
        self.options = data.get("options", {})
        self.requires = data.get("requires", [])


class _RecipeUploadData:
    def __init__(self, ref, prefs=None):
        self.ref = ref
        self.upload = True
        self.force = None
        self.dirty = None
        self.build_always = None
        self.files = None
        self.packages = [_PackageUploadData(p) for p in prefs or []]

    def serialize(self):
        return {
            "ref": repr(self.ref),
            "dirty": self.dirty,
            "upload": self.upload,
            "force": self.force,
            "build_always": self.build_always,
            "files": self.files,
            "packages": [r.serialize() for r in self.packages]
        }


class _PackageUploadData:
    def __init__(self, pref):
        self.pref = pref
        self.upload = True
        self.files = None
        self.force = None

    def serialize(self):
        return {
            "pref": repr(self.pref),
            "upload": self.upload,
            "force": self.force,
            "files": self.files
        }


class UploadBundle:
    def __init__(self):
        self.recipes: List[_RecipeUploadData] = []

    def serialize(self):
        return [r.serialize() for r in self.recipes]

    def add_ref(self, ref):
        self.recipes.append(_RecipeUploadData(ref))

    def add_prefs(self, prefs):
        refs = defaultdict(list)
        for pref in prefs:
            refs[pref.ref].append(pref)
        for ref, prefs in refs.items():
            self.recipes.append(_RecipeUploadData(ref, prefs))

    @property
    def any_upload(self):
        for r in self.recipes:
            if r.upload:
                return True
            for p in r.packages:
                if p.upload:
                    return True
        return False
