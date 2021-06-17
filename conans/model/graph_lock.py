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


class ConanReference:
    def __init__(self, name=None, version=None, user=None, channel=None, rrev=None,
                 package_id=None, prev=None):
        self.name = name
        self.version = version
        self.user = user
        self.channel = channel
        self.rrev = rrev
        self.package_id = package_id
        self.prev = prev

    def __lt__(self, other):
        return repr(self) < repr(other)

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
        return ConanReference(name, version, user, channel, rrev, package_id, prev)

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
            requires.add(ConanReference.loads(repr(graph_node.ref)))

        self.requires = sorted(requires)
        self.python_requires = sorted(python_requires)
        self.build_requires = sorted(build_requires)

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

            requires.add(ConanReference.loads(repr(graph_node.ref)))

        new_requires = sorted(r for r in requires if r not in self.requires)
        self.requires = new_requires + self.requires

    @staticmethod
    def deserialize(data):
        """ constructs a GraphLock from a json like dict
        """
        graph_lock = GraphLock(deps_graph=None)
        graph_lock.root = data["root"]
        for r in data["requires"]:
            graph_lock.requires.append(ConanReference.loads(r))
        for r in data["python_requires"]:
            graph_lock.python_requires.append(ConanReference.loads(r))
        for r in data["build_requires"]:
            graph_lock.build_requires.append(ConanReference.loads(r))
        return graph_lock

    def serialize(self):
        """ returns the object serialized as a dict of plain python types
        that can be converted to json
        """
        return {"root": self.root,
                "requires": [repr(r) for r in self.requires],
                "python_requires": [repr(r) for r in self.python_requires],
                "build_requires": [repr(r) for r in self.build_requires]}

    def lock_node(self, node, requires, build_requires=False):
        """ apply options and constraints on requirements of a node, given the information from
        the lockfile. Requires remove their version ranges.
        """
        if not node.graph_lock_node:
            # For --build-require case, this is the moment the build require can be locked
            if build_requires and node.recipe == RECIPE_VIRTUAL:
                for require in requires:
                    node_id = self._find_node_by_requirement(require.ref)
                    locked_ref = self._nodes[node_id].ref
                    require.lock(locked_ref, node_id)
            # This node is not locked yet, but if it is relaxed, one requirement might
            # match the root node of the exising lockfile
            # If it is a test_package, with a build_require, it shouldn't even try to find it in
            # lock, build_requires are private, if node is not locked, dont lokk for them
            # https://github.com/conan-io/conan/issues/8744
            # TODO: What if a test_package contains extra requires?
            if self._relaxed and not build_requires:
                for require in requires:
                    locked_id = self._match_relaxed_require(require.ref)
                    if locked_id:
                        locked_node = self._nodes[locked_id]
                        require.lock(locked_node.ref, locked_id)
            return

        locked_node = node.graph_lock_node
        if build_requires:
            locked_requires = locked_node.build_requires or []
        else:
            locked_requires = locked_node.requires or []

        refs = {self._nodes[id_].ref.name: (self._nodes[id_].ref, id_) for id_ in locked_requires}

        for require in requires:
            try:
                locked_ref, locked_id = refs[require.ref.name]
            except KeyError:
                t = "Build-require" if build_requires else "Require"
                msg = "%s '%s' cannot be found in lockfile" % (t, require.ref.name)
                if self._relaxed:
                    node.conanfile.output.warn(msg)
                else:
                    raise ConanException(msg)
            else:
                require.lock(locked_ref, locked_id)

        # Check all refs are locked (not checking build_requires atm, as they come from
        # 2 sources (profile, recipe), can't be checked at once
        if not self._relaxed and not build_requires:
            declared_requires = set([r.ref.name for r in requires])
            for require in locked_requires:
                req_node = self._nodes[require]
                if req_node.ref.name not in declared_requires:
                    raise ConanException("'%s' locked requirement '%s' not found"
                                         % (str(node.ref), str(req_node.ref)))

    def check_locked_build_requires(self, node, package_build_requires, profile_build_requires):
        if self._relaxed:
            return
        locked_node = node.graph_lock_node
        locked_requires = locked_node.build_requires
        if not locked_requires:
            return
        package_br = [r for r, _ in package_build_requires]
        profile_br = [r.name for r, _ in profile_build_requires]
        declared_requires = set(package_br + profile_br)
        for require in locked_requires:
            req_node = self._nodes[require]
            if req_node.ref.name not in declared_requires:
                raise ConanException("'%s' locked requirement '%s' not found"
                                     % (str(node.ref), str(req_node.ref)))

    def python_requires(self, node_id):
        if node_id is None and self._relaxed:
            return None
        return self._nodes[node_id].python_requires

    def _match_relaxed_require(self, ref):
        assert self._relaxed
        assert isinstance(ref, ConanFileReference)

        version = ref.version
        version_range = None
        if version.startswith("[") and version.endswith("]"):
            version_range = version[1:-1]

        if version_range:
            for id_, node in self._nodes.items():
                root_ref = node.ref
                if (root_ref is not None and ref.name == root_ref.name and
                        ref.user == root_ref.user and
                        ref.channel == root_ref.channel):
                    output = []
                    result = satisfying([str(root_ref.version)], version_range, output)
                    if result:
                        return id_
        else:
            search_ref = repr(ref)
            if ref.revision:  # Search by exact ref (with RREV)
                node_id = self._find_first(lambda n: n.ref and repr(n.ref) == search_ref)
            else:  # search by ref without RREV
                node_id = self._find_first(lambda n: n.ref and str(n.ref) == search_ref)
            if node_id:
                return node_id

    def _find_first(self, predicate):
        """ find the first node in the graph matching the predicate"""
        for id_, node in sorted(self._nodes.items()):
            if predicate(node):
                return id_

    def get_consumer(self, ref):
        """ given a REF of a conanfile.txt (None) or conanfile.py in user folder,
        return the Node of the package in the lockfile that correspond to that
        REF, or raise if it cannot find it.
        First, search with REF without revisions is done, then approximate search by just name
        """
        assert (ref is None or isinstance(ref, ConanFileReference))

        # None reference
        if ref is None or ref.name is None:
            # Is a conanfile.txt consumer
            node_id = self._find_first(lambda n: not n.ref and n.path)
            if node_id:
                return node_id
        else:
            assert ref.revision is None

            repr_ref = repr(ref)
            str_ref = str(ref)
            node_id = (  # First search by exact ref with RREV
                       self._find_first(lambda n: n.ref and repr(n.ref) == repr_ref) or
                       # If not mathing, search by exact ref without RREV
                       self._find_first(lambda n: n.ref and str(n.ref) == str_ref) or
                       # Or it could be a local consumer (n.path defined), search only by name
                       self._find_first(lambda n: n.ref and n.ref.name == ref.name and n.path))
            if node_id:
                return node_id

        if not self._relaxed:
            raise ConanException("Couldn't find '%s' in lockfile" % ref.full_str())

    def find_require_and_lock(self, reference, conanfile, lockfile_node_id=None):
        if lockfile_node_id:
            node_id = lockfile_node_id
        else:
            node_id = self._find_node_by_requirement(reference)
            if node_id is None:  # relaxed and not found
                return

        locked_ref = self._nodes[node_id].ref
        assert locked_ref is not None
        conanfile.requires[reference.name].lock(locked_ref, node_id)

    def _find_node_by_requirement(self, ref):
        """
        looking for a pkg that will be depended from a "virtual" conanfile
         - "conan install zlib/[>1.2]@"  Version-range NOT allowed
         - "conan install zlib/1.2@ "    Exact dep

        :param ref:
        :return:
        """
        assert isinstance(ref, ConanFileReference), "ref '%s' is '%s'!=ConanFileReference" \
                                                    % (ref, type(ref))

        version = ref.version
        if version.startswith("[") and version.endswith("]"):
            raise ConanException("Version ranges not allowed in '%s' when using lockfiles"
                                 % str(ref))

        # The ``create`` command uses this to install pkg/version --build=pkg
        # removing the revision, but it still should match
        search_ref = repr(ref)
        if ref.revision:  # Match should be exact (with RREV)
            node_id = self._find_first(lambda n: n.ref and repr(n.ref) == search_ref)
        else:
            node_id = self._find_first(lambda n: n.ref and str(n.ref) == search_ref)
        if node_id:
            return node_id

        if not self._relaxed:
            raise ConanException("Couldn't find '%s' in lockfile" % ref.full_str())

    def update_ref(self, ref):
        """ when the recipe is exported, it will complete the missing RREV, otherwise it should
        match the existing RREV
        """
        # Filter existing matching
        ref = ConanReference.loads(repr(ref))
        if ref not in self.requires:
            self.requires.insert(0, ref)
