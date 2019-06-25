import json
import os

from conans.client.graph.graph import RECIPE_VIRTUAL, RECIPE_CONSUMER,\
    BINARY_BUILD
from conans.client.profile_loader import _load_profile
from conans.errors import ConanException
from conans.model.ref import PackageReference, ConanFileReference
from conans.util.files import load, save
from conans.model.options import OptionsValues
from platform import node


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


class GraphLockNode(object):
    def __init__(self, pref, python_requires, options, modified):
        self.pref = pref
        self.python_requires = python_requires
        self.options = options
        self.modified = modified

    @staticmethod
    def from_dict(node_json):
        json_pref = node_json["pref"]
        pref = PackageReference.loads(json_pref) if json_pref else None
        python_requires = node_json.get("python_requires")
        if python_requires:
            python_requires = [ConanFileReference.loads(ref) for ref in python_requires]
        options = OptionsValues.loads(node_json["options"])
        modified = node_json.get("modified")
        return GraphLockNode(pref, python_requires, options, modified)

    def as_dict(self):
        result = {}
        result["pref"] = self.pref.full_repr() if self.pref else None
        result["options"] = self.options.dumps()
        if self.python_requires:
            result["python_requires"] = [r.full_repr() for r in self.python_requires]
        if self.modified:
            result["modified"] = True
        return result


class GraphLock(object):

    def __init__(self, graph=None):
        self._nodes = {}  # {numeric id: PREF or None}
        self._edges = {}  # {numeric_id: [numeric_ids]}
        if graph:
            for node in graph.nodes:
                if node.recipe == RECIPE_VIRTUAL:
                    continue
                dependencies = []
                for edge in node.dependencies:
                    dependencies.append(edge.dst.id)
                python_reqs = getattr(node.conanfile, "python_requires", {})
                python_reqs = [r.ref for _, r in python_reqs.items()] if python_reqs else None
                graph_node = GraphLockNode(node.pref if node.ref else None, python_reqs,
                                           node.conanfile.options.values, False)
                self._nodes[node.id] = graph_node
                self._edges[node.id] = dependencies

    def root_node(self):
        total = []
        for list_ids in self._edges.values():
            total.extend(list_ids)
        roots = set(self._edges).difference(total)
        assert len(roots) == 1
        return self._nodes[roots.pop()]

    @staticmethod
    def from_dict(graph_json):
        graph_lock = GraphLock()
        for id_, node in graph_json["nodes"].items():
            graph_lock._nodes[id_] = GraphLockNode.from_dict(node)
        for id_, dependencies in graph_json["edges"].items():
            graph_lock._edges[id_] = dependencies

        return graph_lock

    def as_dict(self):
        result = {}
        nodes = {}
        for id_, node in self._nodes.items():
            nodes[id_] = node.as_dict()
        result["nodes"] = nodes
        result["edges"] = self._edges
        return result

    def update_lock(self, new_lock):
        for id_, node in new_lock._nodes.items():
            if node.modified:
                old_node = self._nodes[id_]
                if old_node.modified:
                    raise ConanException("Lockfile had already modified %s" % str(node.pref))
                self._nodes[id_] = node

    def clean_modified(self):
        for _, node in self._nodes.items():
            node.modified = False

    def _closure_affected(self):
        closure = set()
        current = [id_ for id_, node in self._nodes.items() if node.modified]
        # closure.update(current)
        while current:
            new_current = set()
            for n in current:
                new_neighs = self._inverse_neighbors(n)
                to_add = set(new_neighs).difference(current)
                new_current.update(to_add)
                closure.update(to_add)
            current = new_current

        return closure

    def _inverse_neighbors(self, node_id):
        result = []
        for id_, nodes_ids in self._edges.items():
            if node_id in nodes_ids:
                result.append(id_)
        return result

    def update_check_graph(self, deps_graph, output):
        affected = self._closure_affected()
        for node in deps_graph.nodes:
            if node.recipe == RECIPE_VIRTUAL:
                continue
            lock_node = self._nodes[node.id]
            if lock_node.pref and lock_node.pref.full_repr() != node.pref.full_repr():
                if node.binary == BINARY_BUILD or node.id in affected:
                    lock_node.pref = node.pref
                else:
                    raise ConanException("Mistmatch between lock and graph:\nLock:  %s\nGraph: %s"
                                         % (lock_node.pref.full_repr(), node.pref.full_repr()))

    def lock_node(self, node, requires):
        if node.recipe == RECIPE_VIRTUAL:
            return
        locked_node = self._nodes[node.id]
        prefs = self._dependencies(node.id)
        node.graph_lock_node = locked_node
        node.conanfile.options.values = locked_node.options
        for require in requires:
            # Not new unlocked dependencies at this stage
            locked_pref, locked_id = prefs[require.ref.name]
            require.ref = require.range_ref = locked_pref.ref
            require._locked_id = locked_id

    def pref(self, node_id):
        return self._nodes[node_id].pref

    def python_requires(self, node_id):
        return self._nodes[node_id].python_requires

    def _dependencies(self, node_id):
        # return {pkg_name: PREF}
        return {self._nodes[i].pref.ref.name: (self._nodes[i].pref, i) for i in self._edges[node_id]}

    def get_node(self, ref):
        # None reference
        if ref is None:
            try:
                return self._nodes[None].pref
            except KeyError:
                raise ConanException("Unspecified reference in graph-lock, please specify")

        # First search by ref (without RREV)
        ids = []
        search_ref = str(ref)
        for id_, node in self._nodes.items():
            if node.pref and str(node.pref.ref) == search_ref:
                ids.append(id_)
        if ids:
            if len(ids) == 1:
                return ids[0]
            raise ConanException("There are %s binaries for ref %s" % (len(ids), ref))

        # Search by approximate name
        ids = []
        for id_, node in self._nodes.items():
            if node.pref and node.pref.ref.name == ref.name:
                ids.append(id_)
        if ids:
            if len(ids) == 1:
                return ids[0]
            raise ConanException("There are %s binaries with name %s" % (len(ids), ref.name))

        raise ConanException("Couldn't find '%s' in graph-lock" % ref.full_repr())

    def update_exported_ref(self, node_id, ref):
        lock_node = self._nodes[node_id]
        if lock_node.pref.ref != ref:
            lock_node.pref = PackageReference(ref, lock_node.pref.id)
            lock_node.modified = True

    def find_node(self, node, reference):
        if node.recipe == RECIPE_VIRTUAL:
            assert reference
            node_id = self.get_node(reference)
            pref = self._nodes[node_id].pref
            # Adding a new node, has the problem of
            # python_requires

            for require in node.conanfile.requires.values():
                require._locked_id = node_id
                require.ref = require.range_ref = pref.ref
            return

        assert node.recipe == RECIPE_CONSUMER
        node_id = self.get_node(node.ref)
        node.id = node_id
