import json
import os

from conans.client.graph.graph import RECIPE_VIRTUAL, RECIPE_CONSUMER,\
    BINARY_BUILD
from conans.client.profile_loader import _load_profile
from conans.errors import ConanException
from conans.model.ref import PackageReference, ConanFileReference
from conans.util.files import load, save


LOCKFILE = "conan.lock"


class GraphLockFile(object):

    def __init__(self, profile, graph_lock):
        self.profile = profile
        self.graph_lock = graph_lock

    @staticmethod
    def load(path):
        if not path:
            raise IOError("Invalid path")
        p = os.path.join(path, LOCKFILE)
        if not os.path.isfile(p):
            raise ConanException("Missing conan.lock file: %s" % p)
        content = load(p)
        try:
            return GraphLockFile.loads(content)
        except Exception as e:
            raise ConanException("Error parsing lockfile '{}': {}".format(p, e))

    @staticmethod
    def loads(text):
        graph_json = json.loads(text)
        profile = graph_json["profile"]
        # FIXME: Reading private very ugly
        profile, _ = _load_profile(profile, None, None)
        graph_lock = GraphLock.from_dict(graph_json["graph_lock"])
        graph_lock_file = GraphLockFile(profile, graph_lock)
        return graph_lock_file

    def save(self, folder):
        filename = LOCKFILE
        p = os.path.join(folder, filename)
        serialized_graph_str = self.dumps()
        save(p, serialized_graph_str)

    def dumps(self):
        result = {"profile": self.profile.dumps(),
                  "graph_lock": self.graph_lock.as_dict()}
        return json.dumps(result, indent=True)


class GraphLock(object):

    def __init__(self, graph=None):
        self._nodes = {}  # {numeric id: PREF or None}
        self._edges = {}  # {numeric_id: [numeric_ids]}
        self._python_requires = {}  # {numeric_id: [REFS (with RREV)]}
        if graph:
            for node in graph.nodes:
                if node.recipe == RECIPE_VIRTUAL:
                    continue
                dependencies = []
                for edge in node.dependencies:
                    dependencies.append(edge.dst.id)
                self._nodes[node.id] = node.pref if node.ref else None
                self._edges[node.id] = dependencies
                python_reqs = getattr(node.conanfile, "python_requires", {})
                self._python_requires[node.id] = [r.ref for _, r in python_reqs.items()]

    @staticmethod
    def from_dict(graph_json):
        graph_lock = GraphLock()
        for id_, pref in graph_json["nodes"].items():
            graph_lock._nodes[id_] = PackageReference.loads(pref) if pref else None
        for id_, dependencies in graph_json["edges"].items():
            graph_lock._edges[id_] = dependencies
        for id_, refs in graph_json["python_requires"].items():
            graph_lock._python_requires[id_] = [ConanFileReference.loads(ref) for ref in refs]
        return graph_lock

    def as_dict(self):
        result = {}
        nodes = {}
        for id_, pref in self._nodes.items():
            nodes[id_] = pref.full_repr() if pref else None
        result["nodes"] = nodes
        result["edges"] = self._edges
        result["python_requires"] = {id_: [r.full_repr() for r in reqs]
                                     for id_, reqs in self._python_requires.items() if reqs}
        return result

    def update_check_graph(self, deps_graph, output):
        for node in deps_graph.nodes:
            if node.recipe == RECIPE_VIRTUAL:
                continue
            lock_node_pref = self._nodes[node.id]
            if node.binary == BINARY_BUILD:
                self._nodes[node.id] = node.pref
            else:
                if (lock_node_pref and node.ref and
                        lock_node_pref.full_repr() != node.pref.full_repr()):
                    raise ConanException("Mistmatch between lock and graph:\nLock %s\nGraph: %s"
                                         % (lock_node_pref.full_repr(), node.pref.full_repr()))

    def lock_node(self, node, requires):
        if node.recipe == RECIPE_VIRTUAL:
            return
        prefs = self.dependencies(node.id)
        for require in requires:
            # Not new unlocked dependencies at this stage
            locked_pref, locked_id = prefs[require.ref.name]
            require.ref = require.range_ref = locked_pref.ref
            require._locked_id = locked_id

    def pref(self, node_id):
        return self._nodes[node_id]

    def python_requires(self, node_id):
        return self._python_requires.get(node_id)

    def dependencies(self, node_id):
        # return {pkg_name: PREF}
        return {self._nodes[i].ref.name: (self._nodes[i], i) for i in self._edges[node_id]}

    def get_node(self, ref):
        # None reference
        if ref is None:
            try:
                return self._nodes[None]
            except KeyError:
                raise ConanException("Unspecified reference in graph-lock, please specify")

        # First search by ref (without RREV)
        ids = []
        search_ref = str(ref)
        for id_, pref in self._nodes.items():
            if pref and str(pref.ref) == search_ref:
                ids.append(id_)
        if ids:
            if len(ids) == 1:
                return ids[0]
            raise ConanException("There are %s binaries for ref %s" % (len(ids), ref))

        # Search by approximate name
        ids = []
        for id_, pref in self._nodes.items():
            if pref and pref.ref.name == ref.name:
                ids.append(id_)
        if ids:
            if len(ids) == 1:
                return ids[0]
            raise ConanException("There are %s binaries with name %s" % (len(ids), ref.name))

        raise ConanException("Couldn't find '%s' in graph-lock" % ref.full_repr())

    def update_ref(self, ref):
        node_id = self.get_node(ref)
        pref = self._nodes[node_id]
        self._nodes[node_id] = PackageReference(ref, pref.id)

    def find_node(self, node, reference):
        if node.recipe == RECIPE_VIRTUAL:
            assert reference
            node_id = self.get_node(reference)
            pref = self._nodes[node_id]
            # Adding a new node, has the problem of
            # python_requires

            for require in node.conanfile.requires.values():
                require._locked_id = node_id
                require.ref = require.range_ref = pref.ref
            return

        assert node.recipe == RECIPE_CONSUMER
        node_id = self.get_node(node.ref)
        node.id = node_id
