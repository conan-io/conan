import json
from collections import defaultdict

from conans import DEFAULT_REVISION_V1
from conans.util.dates import valid_iso8601
from conans.client.cache.remote_registry import Remote


class _RecipeMetadata(object):

    def __init__(self):
        self._revision = DEFAULT_REVISION_V1
        self._time = None
        self.properties = {}
        self.remote = None

    @property
    def time(self):
        return self._time

    @time.setter
    def time(self, r):
        if r is not None and not valid_iso8601(r):
            raise ValueError("Invalid time for the revision, not ISO8601 compliant: %s" % r)
        self._time = r

    @property
    def revision(self):
        return self._revision

    @revision.setter
    def revision(self, r):
        self._revision = DEFAULT_REVISION_V1 if r is None else r

    def to_dict(self):
        ret = {"revision": self.revision,
               "remote": self.remote,
               "properties": self.properties,
               "time": self._time}
        return ret

    @staticmethod
    def loads(data):
        ret = _RecipeMetadata()
        ret.revision = data["revision"]
        remote = data.get("remote")
        if remote:
            ret.remote = Remote(remote[0], remote[1], remote[2])
        ret.properties = data["properties"]
        ret.time = data["time"]
        return ret


class _BinaryPackageMetadata(object):

    def __init__(self):
        self._revision = DEFAULT_REVISION_V1
        self._recipe_revision = DEFAULT_REVISION_V1
        self._time = None
        self.properties = {}
        self.remote = None

    @property
    def revision(self):
        return self._revision

    @revision.setter
    def revision(self, r):
        self._revision = DEFAULT_REVISION_V1 if r is None else r

    @property
    def time(self):
        return self._time

    @time.setter
    def time(self, r):
        if r is not None and not valid_iso8601(r):
            raise ValueError("Invalid time for the revision, not ISO8601 compliant: %s" % r)
        self._time = r

    @property
    def recipe_revision(self):
        return self._recipe_revision

    @recipe_revision.setter
    def recipe_revision(self, r):
        self._recipe_revision = DEFAULT_REVISION_V1 if r is None else r

    def to_dict(self):
        ret = {"revision": self.revision,
               "recipe_revision": self.recipe_revision,
               "properties": self.properties,
               "remote": self.remote,
               "time": self.time}
        return ret

    @staticmethod
    def loads(data):
        ret = _BinaryPackageMetadata()
        ret.revision = data.get("revision")
        ret.recipe_revision = data.get("recipe_revision")
        ret.properties = data.get("properties")
        remote = data.get("remote")
        if remote:
            ret.remote = Remote(remote[0], remote[1], remote[2])
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
