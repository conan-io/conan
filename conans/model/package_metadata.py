import json
from collections import defaultdict


class _RecipeMetadata(object):

    def __init__(self):
        self.revision = None
        self.time = None
        self.properties = {}

    def to_dict(self):
        ret = {"revision": self.revision,
               "properties": self.properties,
               "time": self.time}
        return ret

    @staticmethod
    def loads(data):
        ret = _RecipeMetadata()
        ret.revision = data["revision"]
        ret.properties = data["properties"]
        ret.time = data["time"]
        return ret


class _BinaryPackageMetadata(object):

    def __init__(self):
        self.revision = None
        self.time = None
        self.recipe_revision = None
        self.properties = {}

    def to_dict(self):
        ret = {"revision": self.revision,
               "recipe_revision": self.recipe_revision,
               "properties": self.properties,
               "time": self.time}
        return ret

    @staticmethod
    def loads(data):
        ret = _BinaryPackageMetadata()
        ret.revision = data.get("revision")
        ret.recipe_revision = data.get("recipe_revision")
        ret.properties = data.get("properties")
        ret.time = data.get("time")
        return ret


class PackageMetadata(object):

    def __init__(self):
        self.recipe = _RecipeMetadata()
        self.packages = defaultdict(_BinaryPackageMetadata)

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
