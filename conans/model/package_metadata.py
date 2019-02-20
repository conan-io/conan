import json
from collections import defaultdict

from conans import DEFAULT_REVISION_V1


class _RecipeMetadata(object):

    def __init__(self):
        self._revision = None
        self.properties = {}

    @property
    def revision(self):
        return self._revision

    @revision.setter
    def revision(self, r):
        self._revision = r

    def to_dict(self):
        ret = {"revision": self.revision,
               "properties": self.properties}
        return ret

    @staticmethod
    def loads(data):
        ret = _RecipeMetadata()
        ret.revision = data["revision"]
        ret.properties = data["properties"]
        ret.time = data.get("time")
        return ret


class _BinaryPackageMetadata(object):

    def __init__(self):
        self._revision = None
        self._recipe_revision = None
        self.properties = {}

    @property
    def revision(self):
        return self._revision

    @revision.setter
    def revision(self, r):
        self._revision = DEFAULT_REVISION_V1 if r is None else r

    @property
    def recipe_revision(self):
        return self._recipe_revision

    @recipe_revision.setter
    def recipe_revision(self, r):
        self._recipe_revision = DEFAULT_REVISION_V1 if r is None else r

    def to_dict(self):
        ret = {"revision": self.revision,
               "recipe_revision": self.recipe_revision,
               "properties": self.properties}
        return ret

    @staticmethod
    def loads(data):
        ret = _BinaryPackageMetadata()
        ret.revision = data.get("revision")
        ret.recipe_revision = data.get("recipe_revision")
        ret.properties = data.get("properties")
        return ret


class PackageMetadata(object):

    def __init__(self):
        self.recipe = None
        self.packages = None
        self.clear()

    @staticmethod
    def loads(content):
        ret = PackageMetadata()
        data = json.loads(content)
        ret.recipe = _RecipeMetadata.loads(data.get("recipe"))
        for pid, v in data.get("packages").items():
            ret.packages[pid] = _BinaryPackageMetadata.loads(v)
        return ret

    def dumps(self):
        tmp = {"recipe": self.recipe.to_dict(),
               "packages": {k: v.to_dict() for k, v in self.packages.items()}}
        return json.dumps(tmp)

    def __str__(self):
        return self.dumps()

    def __eq__(self, other):
        return self.dumps() == other.dumps()

    def clear(self):
        self.recipe = _RecipeMetadata()
        self.packages = defaultdict(_BinaryPackageMetadata)

    def clear_package(self, package_id):
        if package_id in self.packages:
            del self.packages[package_id]
