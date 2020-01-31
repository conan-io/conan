import json
import os
from collections import OrderedDict

from conans.client.graph.graph import RECIPE_VIRTUAL, RECIPE_CONSUMER,\
    BINARY_BUILD
from conans.client.graph.python_requires import PyRequires
from conans.client.profile_loader import _load_profile
from conans.errors import ConanException
from conans.model.info import PACKAGE_ID_UNKNOWN
from conans.model.options import OptionsValues
from conans.model.ref import PackageReference, ConanFileReference
from conans.util.files import load, save
from conans.model.version import Version


LOCKFILE = "conan.lock"
LOCKFILE_VERSION = "0.3"


class GraphLockFile(object):

    def __init__(self, profile_host, graph_lock):
        self.profile_host = profile_host
        self.graph_lock = graph_lock

    @staticmethod
    def load(path, revisions_enabled):
        if not path:
            raise IOError("Invalid path")
        if not os.path.isfile(path):
            p = os.path.join(path, LOCKFILE)
            if not os.path.isfile(p):
                raise ConanException("Missing lockfile in: %s" % path)
            path = p
        content = load(path)
        try:
            return GraphLockFile.loads(content, revisions_enabled)
        except Exception as e:
            raise ConanException("Error parsing lockfile '{}': {}".format(path, e))

    @staticmethod
    def loads(text, revisions_enabled):
        graph_json = json.loads(text)
        version = graph_json.get("version")
        if version:
            version = Version(version)
            if version < "0.2":
                raise ConanException("This lockfile was created with a previous incompatible "
                                     "version. Please regenerate the lockfile")
            # Do something with it, migrate, raise...
        profile_host = graph_json.get("profile_host") or graph_json["profile"]
        # FIXME: Reading private very ugly
        profile_host, _ = _load_profile(profile_host, None, None)
        graph_lock = GraphLock.from_dict(graph_json["graph_lock"])
        graph_lock.revisions_enabled = revisions_enabled
        graph_lock_file = GraphLockFile(profile_host, graph_lock)
        return graph_lock_file

    def save(self, path):
        if not path.endswith(".lock"):
            path = os.path.join(path, LOCKFILE)
        serialized_graph_str = self.dumps()
        save(path, serialized_graph_str)

    def dumps(self):
        result = {"profile_host": self.profile_host.dumps(),
                  "graph_lock": self.graph_lock.as_dict(),
                  "version": LOCKFILE_VERSION}
        return json.dumps(result, indent=True)


class GraphLockNode(object):
    # if recipe is exported, it will modify lockfile. No packageID or prev
    MODIFIED_EXPORTED = "exported"
    MODIFIED_BUILT = "built"

    def __init__(self, pref, python_requires, options, requires, build_requires, path,
                 modified=None):
        self.pref = pref
        self.python_requires = python_requires
        self.options = options
        self.modified = modified  # variable
        self.requires = requires
        self.build_requires = build_requires
        self.path = path

    @staticmethod
    def from_dict(data):
        """ constructs a GraphLockNode from a json like dict
        """
        json_pref = data["pref"]
        pref = PackageReference.loads(json_pref, validate=False) if json_pref else None
        python_requires = data.get("python_requires")
        if python_requires:
            python_requires = [ConanFileReference.loads(ref, validate=False)
                               for ref in python_requires]
        options = OptionsValues.loads(data["options"])
        modified = data.get("modified")
        requires = data.get("requires", [])
        build_requires = data.get("build_requires", [])
        path = data.get("path")
        return GraphLockNode(pref, python_requires, options, requires, build_requires, path,
                             modified)

    def as_dict(self):
        """ returns the object serialized as a dict of plain python types
        that can be converted to json
        """
        result = {"pref": repr(self.pref) if self.pref else None,
                  "options": self.options.dumps()}
        if self.python_requires:
            result["python_requires"] = [repr(r) for r in self.python_requires]
        if self.modified:
            result["modified"] = self.modified
        if self.requires:
            result["requires"] = self.requires
        if self.build_requires:
            result["build_requires"] = self.build_requires
        if self.path:
            result["path"] = self.path
        return result


class GraphLock(object):

    def __init__(self, graph=None):
        self._nodes = {}  # {numeric id: PREF or None}
        self.revisions_enabled = None

        if graph is not None:
            for node in graph.nodes:
                if node.recipe == RECIPE_VIRTUAL:
                    continue
                self._upsert_node(node)

    def _upsert_node(self, node):
        requires = []
        build_requires = []
        for edge in node.dependencies:
            if edge.build_require:
                build_requires.append(edge.dst.id)
            else:
                requires.append(edge.dst.id)
        # It is necessary to lock the transitive python-requires too, for this node
        python_reqs = None
        reqs = getattr(node.conanfile, "python_requires", {})
        if isinstance(reqs, dict):  # Old python_requires
            python_reqs = {}
            while reqs:
                python_reqs.update(reqs)
                partial = {}
                for req in reqs.values():
                    partial.update(getattr(req.conanfile, "python_requires", {}))
                reqs = partial

            python_reqs = [r.ref for _, r in python_reqs.items()]
        elif isinstance(reqs, PyRequires):
            # If py_requires are defined, they overwrite old python_reqs
            python_reqs = node.conanfile.python_requires.all_refs()

        previous = node.graph_lock_node
        modified = node.graph_lock_node.modified if node.graph_lock_node else None
        graph_node = GraphLockNode(node.pref if node.ref else None, python_reqs,
                                   node.conanfile.options.values, requires, build_requires,
                                   node.path, modified)
        node.graph_lock_node = graph_node
        self._nodes[node.id] = graph_node

    @property
    def initial_counter(self):
        # IDs are string, we need to compute the maximum
        return max(int(x) for x in self._nodes.keys())

    def root_node_ref(self):
        """ obtain the node in the graph that is not depended by anyone else,
        i.e. the root or downstream consumer
        Used by graph build-order command
        """
        total = []
        for node in self._nodes.values():
            total.extend(node.requires)
            total.extend(node.build_requires)
        roots = set(self._nodes).difference(total)
        assert len(roots) == 1
        root_node = self._nodes[roots.pop()]
        if root_node.path:
            return root_node.path
        if not self.revisions_enabled:
            return root_node.pref.ref.copy_clear_rev()
        return root_node.pref.ref

    @staticmethod
    def from_dict(data):
        """ constructs a GraphLock from a json like dict
        """
        graph_lock = GraphLock()
        for id_, node in data["nodes"].items():
            graph_lock._nodes[id_] = GraphLockNode.from_dict(node)

        return graph_lock

    def as_dict(self):
        """ returns the object serialized as a dict of plain python types
        that can be converted to json
        """
        nodes = OrderedDict()  # Serialized ordered, so lockfiles are more deterministic
        # Sorted using the IDs as integers
        for id_, node in sorted(self._nodes.items(), key=lambda x: int(x[0])):
            nodes[id_] = node.as_dict()
        return {"nodes": nodes}

    def update_lock(self, new_lock):
        """ update the lockfile with the contents of other one that was branched from this
        one and had some node re-built. Only nodes marked as modified (has
        been exported or re-built), will be processed and updated.
        """
        for id_, node in new_lock._nodes.items():
            if node.modified:
                self._nodes[id_] = node

    def _closure_affected(self):
        """ returns all the IDs of the nodes that depend directly or indirectly of some
        package marked as "modified"
        """
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
        """ return all the nodes that have an edge to the "node_id". Useful for computing
        the set of nodes affected downstream by a change in one package
        """
        result = []
        for id_, node in self._nodes.items():
            if node_id in node.requires:
                result.append(id_)
            if node_id in node.build_requires:
                result.append(id_)
        return result

    def update_check_graph(self, deps_graph, output):
        """ update the lockfile, checking for security that only nodes that are being built
        from sources can change their PREF, or nodes that depend on some other "modified"
        package, because their binary-id can change too
        """

        affected = self._closure_affected()
        for node in deps_graph.nodes:
            if node.recipe == RECIPE_VIRTUAL:
                continue
            try:
                lock_node = self._nodes[node.id]
            except KeyError:
                if node.recipe == RECIPE_CONSUMER:
                    continue  # If the consumer node is not found, could be a test_package
                raise
            if lock_node.pref:
                pref = lock_node.pref if self.revisions_enabled else lock_node.pref.copy_clear_revs()
                node_pref = node.pref if self.revisions_enabled else node.pref.copy_clear_revs()
                # If the update is compatible (resolved complete PREV) or if the node has
                # been build, then update the graph
                if (pref.id == PACKAGE_ID_UNKNOWN or pref.is_compatible_with(node_pref) or
                        node.binary == BINARY_BUILD or node.id in affected or
                        node.recipe == RECIPE_CONSUMER):
                    self._upsert_node(node)
                else:
                    raise ConanException("Mismatch between lock and graph:\nLock:  %s\nGraph: %s"
                                         % (repr(pref), repr(node.pref)))

    def pre_lock_node(self, node):
        if node.recipe == RECIPE_VIRTUAL:
            return
        try:
            locked_node = self._nodes[node.id]
        except KeyError:  # If the consumer node is not found, could be a test_package
            if node.recipe == RECIPE_CONSUMER:
                return
            raise ConanException("The node ID %s was not found in the lock" % node.id)

        node.graph_lock_node = locked_node
        node.conanfile.options.values = locked_node.options

    def lock_node(self, node, requires, build_requires=False):
        """ apply options and constraints on requirements of a node, given the information from
        the lockfile. Requires remove their version ranges.
        """
        if not node.graph_lock_node:
            return
        locked_node = node.graph_lock_node
        if build_requires:
            locked_requires = locked_node.build_requires or []
        else:
            locked_requires = locked_node.requires or []
        if self.revisions_enabled:
            prefs = {self._nodes[id_].pref.ref.name: (self._nodes[id_].pref, id_)
                     for id_ in locked_requires}
        else:
            prefs = {self._nodes[id_].pref.ref.name: (self._nodes[id_].pref.copy_clear_revs(), id_)
                     for id_ in locked_requires}

        for require in requires:
            try:
                locked_pref, locked_id = prefs[require.ref.name]
                require.lock(locked_pref.ref, locked_id)
            except KeyError:
                msg = "'%s' cannot be found in lockfile for this package\n" % require.ref.name
                if build_requires:
                    msg += "Make sure it was locked with --build arguments while creating lockfile"
                else:
                    msg += "If it is a new requirement, you need to create a new lockile"
                raise ConanException(msg)

    def python_requires(self, node_id):
        if self.revisions_enabled:
            return self._nodes[node_id].python_requires
        return [r.copy_clear_rev() for r in self._nodes[node_id].python_requires or []]

    def pref(self, node_id):
        return self._nodes[node_id].pref

    def get_node(self, ref):
        """ given a REF, return the Node of the package in the lockfile that correspond to that
        REF, or raise if it cannot find it.
        First, search with REF without revisions is done, then approximate search by just name
        """
        # None reference
        if ref is None:
            # Is a conanfile.txt consumer
            for id_, node in self._nodes.items():
                if not node.pref and node.path:
                    return id_

        # First search by ref (without RREV)
        ids = []
        search_ref = repr(ref)
        for id_, node in self._nodes.items():
            if node.pref and repr(node.pref.ref) == search_ref:
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

        raise ConanException("Couldn't find '%s' in graph-lock" % ref.full_str())

    def update_exported_ref(self, node_id, ref):
        """ when the recipe is exported, it will change its reference, typically the RREV, and
        the lockfile needs to be updated. The lockfile reference will lose PREV information and
        be marked as modified
        """
        lock_node = self._nodes[node_id]
        if lock_node.pref.ref != ref:
            lock_node.pref = PackageReference(ref, lock_node.pref.id)
            lock_node.modified = GraphLockNode.MODIFIED_EXPORTED
