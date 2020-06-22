import json
import os
from collections import OrderedDict

from conans import DEFAULT_REVISION_V1
from conans.client.graph.graph import RECIPE_VIRTUAL, RECIPE_CONSUMER
from conans.client.graph.python_requires import PyRequires
from conans.client.profile_loader import _load_profile
from conans.errors import ConanException
from conans.model.options import OptionsValues
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.version import Version
from conans.util.files import load, save

LOCKFILE = "conan.lock"
LOCKFILE_VERSION = "0.4"


class GraphLockFile(object):

    def __init__(self, profile_host, profile_build, graph_lock):
        self.profile_host = profile_host
        self.profile_build = profile_build
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
        profile_host = graph_json.get("profile_host") or graph_json.get("profile")
        profile_build = graph_json.get("profile_build", None)
        # FIXME: Reading private very ugly
        if profile_host:
            profile_host, _ = _load_profile(profile_host, None, None)
        if profile_build:
            profile_build, _ = _load_profile(profile_build, None, None)
        graph_lock = GraphLock.deserialize(graph_json["graph_lock"], revisions_enabled)
        graph_lock_file = GraphLockFile(profile_host, profile_build, graph_lock)
        return graph_lock_file

    def save(self, path):
        if not path.endswith(".lock"):
            path = os.path.join(path, LOCKFILE)
        serialized_graph_str = self.dumps()
        save(path, serialized_graph_str)

    def dumps(self):
        result = {"profile_host": self.profile_host.dumps(),
                  "graph_lock": self.graph_lock.serialize(),
                  "version": LOCKFILE_VERSION}
        if self.profile_build:
            result["profile_build"] = self.profile_build.dumps()
        if self.graph_lock.only_recipe:
            result.pop("profile_host", None)
            result.pop("profile_build", None)
        return json.dumps(result, indent=True)


class GraphLockNode(object):
    MODIFIED_BUILT = "built"

    def __init__(self, ref, package_id, prev, python_requires, options, requires, build_requires,
                 path, revisions_enabled, modified=None):
        self._ref = ref if ref and ref.name else None  # includes rrev
        self._package_id = package_id
        self._prev = prev
        self.requires = requires
        self.build_requires = build_requires
        self.python_requires = python_requires
        self._options = options
        self._revisions_enabled = revisions_enabled
        self._relaxed = False
        self.modified = modified  # variable
        self._path = path
        if not revisions_enabled:
            if ref:
                self._ref = ref.copy_clear_rev()
            if prev:
                self._prev = DEFAULT_REVISION_V1

    @property
    def relaxed(self):
        return self._relaxed

    @relaxed.setter
    def relaxed(self, value):
        self._relaxed = value

    @property
    def path(self):
        return self._path

    @property
    def ref(self):
        return self._ref

    @ref.setter
    def ref(self, value):
        # only used at export time, to assign rrev
        if not self._revisions_enabled:
            value = value.copy_clear_rev()
        if self._ref:
            if (self._ref.copy_clear_rev() != value.copy_clear_rev() or
                    (self._ref.revision and self._ref.revision != value.revision)):
                raise ConanException("Attempt to modify locked %s to %s"
                                     % (repr(self._ref), repr(value)))

        # Just in case
        self._ref = value
        self._package_id = None
        self._prev = None
        self._path = None

    @property
    def package_id(self):
        return self._package_id

    @package_id.setter
    def package_id(self, value):
        if not self._relaxed and self._package_id is not None and self._package_id != value:
            raise ConanException("Attempt to change package_id of locked '%s'" % repr(self._ref))
        if value != self._package_id:  # When the package_id is being assigned, prev becomes invalid
            self._prev = None
        self._package_id = value

    @property
    def prev(self):
        return self._prev

    @prev.setter
    def prev(self, value):
        if not self._revisions_enabled and value is not None:
            value = DEFAULT_REVISION_V1
        if not self._relaxed and self._prev is not None and self._prev != value:
            raise ConanException("A locked PREV of '%s' was already built" % repr(self._ref))
        self._prev = value

    @property
    def options(self):
        return self._options

    def only_recipe(self):
        self._package_id = None
        self._prev = None
        self._options = None
        self.modified = None

    @staticmethod
    def deserialize(data, revisions_enabled):
        """ constructs a GraphLockNode from a json like dict
        """
        json_ref = data.get("ref")
        ref = ConanFileReference.loads(json_ref) if json_ref else None
        package_id = data.get("package_id")
        prev = data.get("prev")
        python_requires = data.get("python_requires")
        if python_requires:
            python_requires = [ConanFileReference.loads(ref, validate=False)
                               for ref in python_requires]
        options = OptionsValues.loads(data.get("options", ""))
        modified = data.get("modified")
        requires = data.get("requires", [])
        build_requires = data.get("build_requires", [])
        path = data.get("path")
        return GraphLockNode(ref, package_id, prev, python_requires, options, requires,
                             build_requires, path, revisions_enabled, modified)

    def serialize(self):
        """ returns the object serialized as a dict of plain python types
        that can be converted to json
        """
        result = {}
        if self._ref:
            result["ref"] = repr(self._ref)
        if self._options:
            result["options"] = self._options.dumps()
        if self._package_id:
            result["package_id"] = self._package_id
        if self._prev:
            result["prev"] = self._prev
        if self.python_requires:
            result["python_requires"] = [repr(r) for r in self.python_requires]
        if self.modified:
            result["modified"] = self.modified
        if self.requires:
            result["requires"] = self.requires
        if self.build_requires:
            result["build_requires"] = self.build_requires
        if self._path:
            result["path"] = self._path
        return result


class GraphLock(object):

    def __init__(self, deps_graph, revisions_enabled):
        self._nodes = {}  # {id: GraphLockNode}
        self._revisions_enabled = revisions_enabled
        self._relaxed = False  # If True, the lock can be expanded with new Nodes
        self.only_recipe = False

        if deps_graph is not None:
            for graph_node in deps_graph.nodes:
                if graph_node.recipe == RECIPE_VIRTUAL:
                    continue
                self._upsert_node(graph_node)

    @property
    def relaxed(self):
        return self._relaxed

    @relaxed.setter
    def relaxed(self, value):
        self._relaxed = value
        for n in self._nodes.values():
            n.relaxed = value

    def build_order(self):
        levels = []
        opened = list(self._nodes.keys())
        while opened:
            current_level = []
            for o in opened:
                node = self._nodes[o]
                requires = node.requires
                if node.python_requires:
                    requires += node.python_requires
                if node.build_requires:
                    requires += node.build_requires
                if not any(n in opened for n in requires):
                    current_level.append(o)

            current_level.sort()
            levels.append(current_level)
            # now initialize new level
            opened = set(opened).difference(current_level)

        result = []
        total_prefs = set()  # to remove duplicates, same pref shouldn't build twice
        for level in levels:
            new_level = []
            for n in level:
                locked_node = self._nodes[n]
                if locked_node.prev is None and locked_node.package_id is not None:
                    # Manipulate the ref so it can be used directly in install command
                    if not self._revisions_enabled:
                        ref = locked_node.ref.copy_clear_rev()
                        ref = repr(ref)
                        if "@" not in ref:
                            ref += "@"
                    else:
                        ref = locked_node.ref
                        ref = repr(ref)
                        if "@" not in ref:
                            ref = ref.replace("#", "@#")
                    if ref not in total_prefs:
                        new_level.append((n, ref))
                        total_prefs.add(ref)
            if new_level:
                result.append(new_level)

        return result

    def only_recipes(self):
        for node in self._nodes.values():
            node.only_recipe()
        self.only_recipe = True

    def _upsert_node(self, graph_node):
        requires = []
        build_requires = []
        for edge in graph_node.dependencies:
            if edge.build_require:
                build_requires.append(edge.dst.id)
            else:
                requires.append(edge.dst.id)
        # It is necessary to lock the transitive python-requires too, for this node
        python_reqs = None
        reqs = getattr(graph_node.conanfile, "python_requires", {})
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
            python_reqs = graph_node.conanfile.python_requires.all_refs()

        previous = graph_node.graph_lock_node
        modified = previous.modified if previous else None
        ref = graph_node.ref if graph_node.ref and graph_node.ref.name else None
        package_id = graph_node.package_id if ref and ref.revision else None
        prev = graph_node.prev if ref and ref.revision else None
        lock_node = GraphLockNode(ref, package_id, prev, python_reqs,
                                  graph_node.conanfile.options.values, requires,
                                  build_requires, graph_node.path, self._revisions_enabled, modified)
        graph_node.graph_lock_node = lock_node
        self._nodes[graph_node.id] = lock_node

    @property
    def initial_counter(self):
        # IDs are string, we need to compute the maximum integer
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
        return root_node.ref

    @staticmethod
    def deserialize(data, revisions_enabled):
        """ constructs a GraphLock from a json like dict
        """
        revs_enabled = data.get("revisions_enabled", False)
        if revs_enabled != revisions_enabled:
            raise ConanException("Lockfile revisions: '%s' != Current revisions '%s'"
                                 % (revs_enabled, revisions_enabled))
        graph_lock = GraphLock(deps_graph=None, revisions_enabled=revisions_enabled)
        for id_, node in data["nodes"].items():
            graph_lock._nodes[id_] = GraphLockNode.deserialize(node, revisions_enabled)

        return graph_lock

    def serialize(self):
        """ returns the object serialized as a dict of plain python types
        that can be converted to json
        """
        nodes = OrderedDict()  # Serialized ordered, so lockfiles are more deterministic
        # Sorted using the IDs as integers
        for id_, node in sorted(self._nodes.items(), key=lambda x: int(x[0])):
            nodes[id_] = node.serialize()
        return {"nodes": nodes,
                "revisions_enabled": self._revisions_enabled}

    def update_lock(self, new_lock):
        """ update the lockfile with the contents of other one that was branched from this
        one and had some node re-built. Only nodes marked as modified (has
        been exported or re-built), will be processed and updated.
        """
        for id_, node in new_lock._nodes.items():
            if node.modified:
                self._nodes[id_] = node

    def clean_modified(self):
        """ remove all the "modified" flags from the lockfile
        """
        for _, node in self._nodes.items():
            node.modified = None

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

    def pre_lock_node(self, node):
        if node.recipe == RECIPE_VIRTUAL:
            return
        try:
            locked_node = self._nodes[node.id]
        except KeyError:  # If the consumer node is not found, could be a test_package
            if node.recipe == RECIPE_CONSUMER:
                return
            if self._relaxed:
                node.conanfile.output.warn("Package can't be locked, not found in the lockfile")
                return
            else:
                raise ConanException("The node %s ID %s was not found in the lock"
                                     % (node.ref, node.id))

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

        refs = {self._nodes[id_].ref.name: (self._nodes[id_].ref, id_) for id_ in locked_requires}

        for require in requires:
            try:
                locked_ref, locked_id = refs[require.ref.name]
                require.lock(locked_ref, locked_id)
            except KeyError:
                t = "Build-require" if build_requires else "Require"
                msg = "%s '%s' cannot be found in lockfile" % (t, require.ref.name)
                if self._relaxed:
                    node.conanfile.output.warn(msg)
                else:
                    raise ConanException(msg)

        # Check all refs are locked
        if not self._relaxed:
            declared_requires = set([r.ref.name for r in requires])
            for require in locked_node.requires:
                req_node = self._nodes[require]
                if req_node.ref.name not in declared_requires:
                    raise ConanException("'%s' locked requirement '%s' not found"
                                         % (str(node.ref), str(req_node.ref)))

    def python_requires(self, node_id):
        if self._revisions_enabled:
            return self._nodes[node_id].python_requires
        return [r.copy_clear_rev() for r in self._nodes[node_id].python_requires or []]

    def ref(self, node_id):
        return self._nodes[node_id].ref

    def get_node(self, ref):
        """ given a REF, return the Node of the package in the lockfile that correspond to that
        REF, or raise if it cannot find it.
        First, search with REF without revisions is done, then approximate search by just name
        """
        # None reference
        if ref is None or ref.name is None:
            # Is a conanfile.txt consumer
            for id_, node in self._nodes.items():
                if not node.ref and node.path:
                    return id_

        # First search by ref (without RREV)
        ids = []
        search_ref = repr(ref)
        for id_, node in self._nodes.items():
            if node.ref and repr(node.ref) == search_ref:
                ids.append(id_)
        if ids:
            if len(ids) == 1:
                return ids[0]
            raise ConanException("There are %s binaries for ref %s" % (len(ids), ref))

        # Search by approximate name
        ids = []
        for id_, node in self._nodes.items():
            if node.ref and node.ref.name == ref.name:
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
        print("UPDATING EXPORT ", ref, node_id)
        lock_node.ref = ref
