import json
import os
from collections import OrderedDict

from conans import DEFAULT_REVISION_V1
from conans.client.graph.graph import RECIPE_VIRTUAL, RECIPE_CONSUMER
from conans.client.graph.python_requires import PyRequires
from conans.client.graph.range_resolver import satisfying
from conans.client.profile_loader import _load_profile
from conans.errors import ConanException
from conans.model.info import PACKAGE_ID_UNKNOWN
from conans.model.options import OptionsValues
from conans.model.ref import ConanFileReference
from conans.util.files import load, save

LOCKFILE = "conan.lock"
LOCKFILE_VERSION = "0.4"


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
    def load(path, revisions_enabled):
        if not path:
            raise IOError("Invalid path")
        if not os.path.isfile(path):
            raise ConanException("Missing lockfile in: %s" % path)
        content = load(path)
        try:
            return GraphLockFile._loads(content, revisions_enabled)
        except Exception as e:
            raise ConanException("Error parsing lockfile '{}': {}".format(path, e))

    def save(self, path):
        serialized_graph_str = self._dumps(path)
        save(path, serialized_graph_str)

    @staticmethod
    def _loads(text, revisions_enabled):
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
        graph_lock = GraphLock.deserialize(graph_json["graph_lock"], revisions_enabled)
        graph_lock_file = GraphLockFile(profile_host, profile_build, graph_lock)
        return graph_lock_file

    def _dumps(self, path):
        # Make the lockfile more reproducible by using a relative path in the node.path
        # At the moment the node.path value is not really used, only its existence
        path = os.path.dirname(path)
        serial_lock = self._graph_lock.serialize()
        for node in serial_lock["nodes"].values():
            p = node.get("path")
            if p:
                try:  # In Windows with different drives D: C: this fails
                    node["path"] = os.path.relpath(p, path)
                except ValueError:
                    pass
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


class GraphLockNode(object):

    def __init__(self, ref, package_id, prev, python_requires, options, requires, build_requires,
                 path, revisions_enabled, context, modified=None):
        self._ref = ref if ref and ref.name else None  # includes rrev
        self._package_id = package_id
        self._context = context
        self._prev = prev
        self._requires = requires
        self._build_requires = build_requires
        if revisions_enabled:
            self._python_requires = python_requires
        else:
            self._python_requires = [r.copy_clear_rev() for r in python_requires or []]
        self._options = options
        self._revisions_enabled = revisions_enabled
        self._relaxed = False
        self._modified = modified  # Exclusively now for "conan_build_info" command
        self._path = path
        if not revisions_enabled:
            if ref:
                self._ref = ref.copy_clear_rev()
            if prev:
                self._prev = DEFAULT_REVISION_V1

    @property
    def context(self):
        return self._context

    @property
    def requires(self):
        return self._requires

    @property
    def modified(self):
        return self._modified

    @property
    def build_requires(self):
        return self._build_requires

    def relax(self):
        self._relaxed = True

    def clean_modified(self):
        self._modified = None

    @property
    def path(self):
        return self._path

    @property
    def ref(self):
        return self._ref

    @property
    def python_requires(self):
        return self._python_requires

    @ref.setter
    def ref(self, value):
        # only used at export time, to assign rrev
        if not self._revisions_enabled:
            value = value.copy_clear_rev()
        if self._ref:
            if (self._ref.copy_clear_rev() != value.copy_clear_rev() or
                    (self._ref.revision and self._ref.revision != value.revision) or
                    self._prev):
                raise ConanException("Attempt to modify locked %s to %s"
                                     % (repr(self._ref), repr(value)))

        self._ref = value
        # Just in case
        self._path = None

    @property
    def package_id(self):
        return self._package_id

    @package_id.setter
    def package_id(self, value):
        if (self._package_id is not None and self._package_id != PACKAGE_ID_UNKNOWN and
                self._package_id != value):
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
        if self._prev is not None:
            raise ConanException("Trying to modify locked package {}".format(repr(self._ref)))
        if value is not None:
            self._modified = True  # Only for conan_build_info
        self._prev = value

    def unlock_prev(self):
        """ for creating a new lockfile from an existing one, when specifying --build, it
        should make prev=None in order to unlock it and allow building again"""
        if self._prev is None:
            return  # Already unlocked
        if not self._relaxed:
            raise ConanException("Cannot build '%s' because it is already locked in the "
                                 "input lockfile" % repr(self._ref))
        self._prev = None

    def complete_base_node(self, package_id, prev):
        # completing a node from a base lockfile shouldn't mark the node as modified
        self.package_id = package_id
        self.prev = prev
        self._modified = None

    @property
    def options(self):
        return self._options

    def only_recipe(self):
        self._package_id = None
        self._prev = None
        self._options = None
        self._modified = None

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
            python_requires = [ConanFileReference.loads(py_req, validate=False)
                               for py_req in python_requires]
        options = data.get("options")
        options = OptionsValues.loads(options) if options else None
        modified = data.get("modified")
        context = data.get("context")
        requires = data.get("requires", [])
        build_requires = data.get("build_requires", [])
        path = data.get("path")
        return GraphLockNode(ref, package_id, prev, python_requires, options, requires,
                             build_requires, path, revisions_enabled, context, modified)

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
        if self._modified:
            result["modified"] = self._modified
        if self._requires:
            result["requires"] = self._requires
        if self._build_requires:
            result["build_requires"] = self._build_requires
        if self._path:
            result["path"] = self._path
        if self._context:
            result["context"] = self._context
        return result


class GraphLock(object):

    def __init__(self, deps_graph, revisions_enabled):
        self._nodes = {}  # {id: GraphLockNode}
        self._revisions_enabled = revisions_enabled
        self._relaxed = False  # If True, the lock can be expanded with new Nodes

        if deps_graph is None:
            return

        for graph_node in deps_graph.nodes:
            if graph_node.recipe == RECIPE_VIRTUAL:
                continue

            # Creating a GraphLockNode from the existing DepsGraph node
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
                python_reqs = graph_node.conanfile.python_requires.all_refs()

            ref = graph_node.ref if graph_node.ref and graph_node.ref.name else None
            package_id = graph_node.package_id if ref and ref.revision else None
            prev = graph_node.prev if ref and ref.revision else None
            # Make sure to inherit the modified flag in case it is a partial lock
            modified = graph_node.graph_lock_node.modified if graph_node.graph_lock_node else None
            lock_node = GraphLockNode(ref, package_id, prev, python_reqs,
                                      graph_node.conanfile.options.values, requires, build_requires,
                                      graph_node.path, self._revisions_enabled, graph_node.context,
                                      modified=modified)

            graph_node.graph_lock_node = lock_node
            self._nodes[graph_node.id] = lock_node

    @property
    def nodes(self):
        return self._nodes

    def relax(self):
        """ A lockfile is strict in its topology. It cannot add new nodes, have non-locked
        requirements or have unused locked requirements. This method is called only:
        - With "conan lock create --lockfile=existing --lockfile-out=new
        - for the "test_package" functionality, as test_package/conanfile.py can have requirements
          and those will never exist in the lockfile
        """
        self._relaxed = True
        for n in self._nodes.values():
            n.relax()

    @property
    def relaxed(self):
        return self._relaxed

    def clean_modified(self):
        for n in self._nodes.values():
            n.clean_modified()

    def build_order(self):
        """ This build order uses empty PREVs to decide which packages need to be built

        :return: An ordered list of lists, each inner element is a tuple with the node ID and the
                 reference (as string), possibly including revision, of the node
        """
        # First do a topological order by levels, the ids of the nodes are stored
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

        # Now compute the list of list with prev=None, and prepare them with the right
        # references to be used in cmd line
        result = []
        total_prefs = set()  # to remove duplicates, same pref shouldn't build twice
        for level in levels:
            new_level = []
            for id_ in level:
                locked_node = self._nodes[id_]
                if locked_node.prev is None and locked_node.package_id is not None:
                    # Manipulate the ref so it can be used directly in install command
                    ref = repr(locked_node.ref)
                    if not self._revisions_enabled:
                        if "@" not in ref:
                            ref += "@"
                    else:
                        if "@" not in ref:
                            ref = ref.replace("#", "@#")
                    if (ref, locked_node.package_id, locked_node.context) not in total_prefs:
                        new_level.append((ref, locked_node.package_id, locked_node.context, id_))
                        total_prefs.add((ref, locked_node.package_id, locked_node.context))
            if new_level:
                result.append(new_level)

        return result

    def complete_matching_prevs(self):
        """ when a build_require that has the same ref and package_id is built, only one node
        gets its PREV updated. This method fills the repeated nodes missing PREV to the same one.
        The build-order only returned 1 node (matching ref:package_id).
        """
        groups = {}
        for node in self._nodes.values():
            groups.setdefault((node.ref, node.package_id), []).append(node)

        for nodes in groups.values():
            if len(nodes) > 1:
                prevs = set(node.prev for node in nodes if node.prev)
                if prevs:
                    assert len(prevs) == 1, "packages in lockfile with different PREVs"
                    prev = prevs.pop()
                    for node in nodes:
                        if node.prev is None:
                            node.prev = prev

    def only_recipes(self):
        """ call this method to remove the packages/binaries information from the lockfile, and
        keep only the reference version and RREV. A lockfile with this stripped information can
        be used for creating new lockfiles based on it
        """
        for node in self._nodes.values():
            node.only_recipe()

    @property
    def initial_counter(self):
        """ When a new, relaxed graph is being created based on this lockfile, it can add new
        nodes. The IDs of those nodes need a base ID, to not collide with the existing ones

        :return: the maximum ID of this lockfile, as integer
        """
        # IDs are string, we need to compute the maximum integer
        return max(int(x) for x in self._nodes.keys())

    def root_node_id(self):
        # Compute the downstream root
        total = []
        for node in self._nodes.values():
            total.extend(node.requires)
            total.extend(node.build_requires)
        roots = set(self._nodes).difference(total)
        assert len(roots) == 1
        root_id = roots.pop()
        return root_id

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
        one and had some node re-built. Only missing package_id and PREV information will be
        updated, the references must match or it will be an error. The nodes IDS must match too.
        """
        for id_, node in new_lock.nodes.items():
            current = self._nodes[id_]
            if current.ref:
                if node.ref.copy_clear_rev() != current.ref.copy_clear_rev():
                    raise ConanException("Incompatible reference")
            if current.package_id is None or current.package_id == PACKAGE_ID_UNKNOWN:
                current.package_id = node.package_id
            if current.prev is None:
                current.prev = node.prev

    def pre_lock_node(self, node):
        if node.recipe == RECIPE_VIRTUAL:
            return
        try:
            locked_node = self._nodes[node.id]
        except KeyError:  # If the consumer node is not found, could be a test_package
            if node.recipe == RECIPE_CONSUMER:
                return
            if not self._relaxed:
                raise ConanException("The node %s ID %s was not found in the lock"
                                     % (node.ref, node.id))
        else:
            node.graph_lock_node = locked_node
            if locked_node.options is not None:  # This was a "partial" one, not a "base" one
                node.conanfile.options.values = locked_node.options

    def lock_node(self, node, requires, build_requires=False):
        """ apply options and constraints on requirements of a node, given the information from
        the lockfile. Requires remove their version ranges.
        """
        # Important to remove the overrides, they do not need to be locked or evaluated
        requires = [r for r in requires if not r.override]
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
        if locked_node is None:
            return
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

    def update_exported_ref(self, node_id, ref):
        """ when the recipe is exported, it will complete the missing RREV, otherwise it should
        match the existing RREV
        """
        lock_node = self._nodes[node_id]
        lock_node.ref = ref
