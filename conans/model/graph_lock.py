import json
import os
from collections import OrderedDict

from conans.client.graph.graph import RECIPE_VIRTUAL, RECIPE_CONSUMER
from conans.client.graph.python_requires import PyRequires
from conans.client.graph.range_resolver import satisfying
from conans.client.profile_loader import _load_profile
from conans.errors import ConanException
from conans.model.info import PACKAGE_ID_UNKNOWN
from conans.model.options import OptionsValues
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.version import Version
from conans.util.files import load, save

LOCKFILE = "conan.lock"
LOCKFILE_VERSION = "0.5"


class GraphLockFile(object):

    def __init__(self, profile_host, profile_build, graph_lock):
        self._profile_host = profile_host
        self._profile_build = profile_build
        self._graph_lock = graph_lock

    @property
    def graph_lock(self):
        return self._graph_lock

    @property
    def profile_host(self):
        return self._profile_host

    @property
    def profile_build(self):
        return self._profile_build

    @staticmethod
    def load(path):
        if not path:
            raise IOError("Invalid path")
        if not os.path.isfile(path):
            raise ConanException("Missing lockfile in: %s" % path)
        content = load(path)
        try:
            return GraphLockFile._loads(content)
        except Exception as e:
            raise ConanException("Error parsing lockfile '{}': {}".format(path, e))

    def save(self, path):
        serialized_graph_str = self._dumps(path)
        save(path, serialized_graph_str)

    @staticmethod
    def _loads(text):
        graph_json = json.loads(text)
        version = graph_json.get("version")
        if version:
            if version != LOCKFILE_VERSION:
                raise ConanException("This lockfile was created with an incompatible "
                                     "version. Please regenerate the lockfile")
            # Do something with it, migrate, raise...
        profile_host = graph_json.get("profile_host", None)
        profile_build = graph_json.get("profile_build", None)
        # FIXME: Reading private very ugly
        if profile_host:
            profile_host, _ = _load_profile(profile_host, None, None)
        if profile_build:
            profile_build, _ = _load_profile(profile_build, None, None)
        graph_lock = GraphLock.deserialize(graph_json["graph_lock"])
        graph_lock_file = GraphLockFile(profile_host, profile_build, graph_lock)
        return graph_lock_file

    def _dumps(self, path):
        # Make the lockfile more reproducible by using a relative path in the node.path
        # At the moment the node.path value is not really used, only its existence
        serial_lock = self._graph_lock.serialize()
        result = {"graph_lock": serial_lock,
                  "version": LOCKFILE_VERSION}
        if self._profile_host:
            result["profile_host"] = self._profile_host.dumps()
        if self._profile_build:
            result["profile_build"] = self._profile_build.dumps()
        return json.dumps(result, indent=True)

    def only_recipes(self):
        self._graph_lock.only_recipes()
        self._profile_host = None
        self._profile_build = None


class ConanLockReference:
    def __init__(self, name, version, user=None, channel=None, rrev=None,
                 package_id=None, prev=None):
        self.name = name
        self.version = Version(version)
        self.user = user
        self.channel = channel
        self.rrev = rrev
        self.package_id = package_id
        self.prev = prev

    def __lt__(self, other):
        return (self.name, self.version, self.user, self.channel, self.rrev, self.package_id,
                self.prev) \
               < \
               (other.name, other.version, other.user, other.channel, other.rrev, other.package_id,
                other.prev)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return self.__dict__ != other.__dict__

    def __hash__(self):
        return hash((self.name, self.version, self.user, self.channel, self.rrev,
                     self.package_id, self.prev))

    @staticmethod
    def loads(text):
        tokens = text.split(":", 1)
        if len(tokens) == 2:
            ref = tokens[0]
            tokens = tokens[1].split("#", 1)
            if len(tokens) == 2:
                package_id, prev = tokens
            else:
                package_id = tokens[0]
                prev = None
        else:
            ref = text
            package_id = prev = None

        tokens = ref.split("#", 1)
        if len(tokens) == 2:
            ref = tokens[0]
            rrev = tokens[1]
        else:
            rrev = None

        tokens = ref.split("@", 1)
        if len(tokens) == 2:
            ref = tokens[0]
            user, channel = tokens[1].split("/", 1)
        else:
            user = channel = None

        name, version = ref.split("/", 1)
        return ConanLockReference(name, version, user, channel, rrev, package_id, prev)

    def __repr__(self):
        if self.name is None:
            return ""
        result = "/".join([self.name, self.version])
        if self.user:
            result += "@{}/{}".format(self.user, self.channel)
        if self.rrev:
            result += "#{}".format(self.rrev)
        if self.package_id:
            result += ":{}".format(self.package_id)
        if self.prev:
            result += "#{}".format(self.prev)
        return result

    def get_ref(self):
        return ConanFileReference(self.name, self.version, self.user, self.channel, self.rrev)


class GraphLock(object):

    def __init__(self, deps_graph):
        self.root = None
        self.requires = []
        self.python_requires = []
        self.build_requires = []

        if deps_graph is None:
            return

        requires = set()
        python_requires = set()
        build_requires = set()
        for graph_node in deps_graph.nodes:
            try:
                python_requires.update(graph_node.conanfile.python_requires.all_refs())
            except AttributeError:
                pass
            if graph_node.recipe in (RECIPE_VIRTUAL, RECIPE_CONSUMER) or graph_node.ref is None:
                continue
            assert graph_node.conanfile is not None

            self.root = self.root or graph_node.ref.name
            requires.add(ConanLockReference.loads(repr(graph_node.ref)))

        self.requires = list(reversed(sorted(requires)))
        self.python_requires = list(reversed(sorted(python_requires)))
        self.build_requires = list(reversed(sorted(build_requires)))

    def only_recipes(self):
        for r in self.requires:
            r.package_id = r.prev = None

    def update(self, deps_graph):
        """ add new things at the beginning, to give more priority
        """
        requires = set()
        for graph_node in deps_graph.nodes:
            if graph_node.recipe == RECIPE_VIRTUAL or graph_node.ref is None:
                continue
            assert graph_node.conanfile is not None

            requires.add(ConanLockReference.loads(repr(graph_node.ref)))

        new_requires = sorted(r for r in requires if r not in self.requires)
        self.requires = list(reversed(sorted(new_requires + self.requires)))

    @staticmethod
    def deserialize(data):
        """ constructs a GraphLock from a json like dict
        """
        graph_lock = GraphLock(deps_graph=None)
        graph_lock.root = data["root"]
        for r in data["requires"]:
            graph_lock.requires.append(ConanLockReference.loads(r))
        for r in data["python_requires"]:
            graph_lock.python_requires.append(ConanLockReference.loads(r))
        for r in data["build_requires"]:
            graph_lock.build_requires.append(ConanLockReference.loads(r))
        return graph_lock

    def serialize(self):
        """ returns the object serialized as a dict of plain python types
        that can be converted to json
        """
        return {"root": self.root,
                "requires": [repr(r) for r in self.requires],
                "python_requires": [repr(r) for r in self.python_requires],
                "build_requires": [repr(r) for r in self.build_requires]}

    def update_ref(self, ref):
        """ when the recipe is exported, it will complete the missing RREV, otherwise it should
        match the existing RREV
        """
        # Filter existing matching
        ref = ConanLockReference.loads(repr(ref))
        if ref not in self.requires:
            self.requires.insert(0, ref)
