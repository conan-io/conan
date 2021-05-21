from enum import Enum

from conans.client.graph.graph_error import GraphError
from conans.errors import ConanException
from conans.model.ref import PackageReference
from conans.model.requires import Requirement, RequirementDict

RECIPE_DOWNLOADED = "Downloaded"
RECIPE_INCACHE = "Cache"  # The previously installed recipe in cache is being used
RECIPE_UPDATED = "Updated"
RECIPE_NEWER = "Newer"  # The local recipe is  modified and newer timestamp than server
RECIPE_NOT_IN_REMOTE = "Not in remote"
RECIPE_UPDATEABLE = "Update available"  # The update of recipe is available (only in conan info)
RECIPE_NO_REMOTE = "No remote"
RECIPE_EDITABLE = "Editable"
RECIPE_CONSUMER = "Consumer"  # A conanfile from the user
RECIPE_VIRTUAL = "Virtual"  # A virtual conanfile (dynamic in memory conanfile)
RECIPE_MISSING = "Missing recipe"  # Impossible to find a recipe for this reference

BINARY_CACHE = "Cache"
BINARY_DOWNLOAD = "Download"
BINARY_UPDATE = "Update"
BINARY_BUILD = "Build"
BINARY_MISSING = "Missing"
BINARY_SKIP = "Skip"
BINARY_EDITABLE = "Editable"
BINARY_UNKNOWN = "Unknown"
BINARY_INVALID = "Invalid"

CONTEXT_HOST = "host"
CONTEXT_BUILD = "build"


class PackageType(Enum):
    LIBRARY = "library"  # abstract type, should contain shared option to define
    STATIC = "static library"
    SHARED = "shared library"
    HEADER = "header library"
    RUN = "run library"
    UNKNOWN = "unknown"


class TransitiveRequirement:
    def __init__(self, require, node):
        self.require = require
        self.node = node

    def __repr__(self):
        return "Require: {}, Node: {}".format(repr(self.require), repr(self.node))


class Node(object):
    def __init__(self, ref, conanfile, context, recipe=None, path=None):
        self.ref = ref
        self.path = path  # path to the consumer conanfile.xx for consumer, None otherwise
        self._package_id = None
        self.prev = None
        if conanfile is not None:
            conanfile._conan_node = self  # Reference to self, to access data
        self.conanfile = conanfile

        self.binary = None
        self.recipe = recipe
        self.remote = None
        self.binary_remote = None
        self.revision_pinned = False  # The revision has been specified by the user
        self.context = context

        self.id = None  # Unique ID (uuid at the moment) of a node in the graph
        self.graph_lock_node = None  # the locking information can be None

        # real graph model
        self.transitive_deps = RequirementDict()  # of _TransitiveRequirement
        self.dependencies = []  # Ordered Edges
        self.dependants = []  # Edges
        self.conflict = None

    def __lt__(self, other):
        # TODO: Remove this order, shouldn't be necessary
        return str(self.ref) < str(other.ref)

    def propagate_closing_loop(self, require, prev_node):
        self.propagate_downstream(require, prev_node)
        # List to avoid mutating the dict
        for transitive in list(prev_node.transitive_deps.values()):
            # TODO: possibly optimize in a bulk propagate
            prev_node.propagate_downstream(transitive.require, transitive.node, self)

    @property
    def package_type(self):
        # This doesnt implement the header_only option without shared one. Users should define
        # their package_type as they wish in the configure() method
        conanfile_type = self.conanfile.package_type
        if conanfile_type is not None:
            conanfile_type = PackageType(conanfile_type)

        if conanfile_type is None:  # automatic default detection with option shared/header-only
            try:
                shared = self.conanfile.options.shared
            except ConanException:
                pass
            else:
                if shared is not None:
                    if shared:
                        return PackageType.SHARED
                    else:
                        try:
                            header = self.conanfile.options.header_only
                        except ConanException:
                            pass
                        else:
                            if header:
                                return PackageType.HEADER
                        return PackageType.STATIC
            return PackageType.UNKNOWN

        if conanfile_type is PackageType.LIBRARY:
            try:
                shared = self.conanfile.options.shared  # MUST exist
            except ConanException:
                raise ConanException("Package type is 'library', but no 'shared' option declared")
            if shared:
                return PackageType.SHARED
            else:
                try:
                    header = self.conanfile.options.header_only
                except ConanException:
                    pass
                else:
                    if header:
                        return PackageType.HEADER
                return PackageType.STATIC

        return conanfile_type

    def _transform_downstream_require(self, require, node, dependant):
        if require.build:  # Build-requires do not propagate anything
            return  # TODO: check this

        if require.public is False:
            # TODO: We could implement checks in case private is violated (e.g shared libs)
            return

        source_require = dependant.require
        up_type = node.package_type if node is not None else None
        current_type = self.package_type

        if source_require.build:  # Build-requires
            print("    Propagating build-require",  self, "<-", require)
            # If the above is shared or the requirement is explicit run=True
            if up_type is PackageType.SHARED or up_type is PackageType.RUN or require.run:
                downstream_require = Requirement(require.ref, include=False, link=False, build=True,
                                                 run=True, public=False,)
                return downstream_require
            return

        # Regular and test requires
        if up_type is PackageType.SHARED or up_type is PackageType.RUN:
            if current_type is PackageType.SHARED:
                downstream_require = Requirement(require.ref, include=False, link=False, run=True)
            elif current_type is PackageType.STATIC:
                downstream_require = Requirement(require.ref, include=False, link=True, run=True)
            elif current_type is PackageType.RUN:
                downstream_require = Requirement(require.ref, include=False, link=False, run=True)
            else:  # unknown
                assert current_type is PackageType.UNKNOWN
                # Consumers will need to find it at build time too
                downstream_require = Requirement(require.ref, include=True, link=True, run=True)
        elif up_type is PackageType.STATIC:
            if current_type is PackageType.SHARED:
                downstream_require = Requirement(require.ref, include=False, link=False, run=False)
            elif current_type is PackageType.RUN:
                downstream_require = Requirement(require.ref, include=False, link=False, run=False)
            elif current_type is PackageType.STATIC:  # static
                downstream_require = Requirement(require.ref, include=False, link=True, run=False)
            else:  # unknown
                assert current_type is PackageType.UNKNOWN
                downstream_require = Requirement(require.ref, include=True, link=True, run=False)
        elif up_type is PackageType.HEADER:
            downstream_require = Requirement(require.ref, include=False, link=False, run=False)
        else:
            # Unknown, default. This happens all the time while check_downstream as shared is unknown
            # FIXME
            downstream_require = require.copy()

        assert require.public, "at this point require should be public"

        if require.transitive_headers:
            downstream_require.include = True

        # If non-default, then the consumer requires has priority
        if source_require.public is False:
            downstream_require.public = False

        if source_require.include is False:
            downstream_require.include = False

        if source_require.link is False:
            downstream_require.link = False

        # TODO: Automatic assignment invalidates user possibility of overriding default
        # if source_require.run is not None:
        #    downstream_require.run = source_require.run

        if source_require.test:
            downstream_require.test = True

        return downstream_require

    def propagate_downstream(self, require, node, prev_node=None):
        # print("  Propagating downstream ", self, "<-", require)
        assert node is not None
        # This sets the transitive_deps node if it was None (overrides)
        # Take into account that while propagating we can find RUNTIME shared conflicts we
        # didn't find at check_downstream_exist, because we didn't know the shared/static
        existing = self.transitive_deps.get(require)
        if existing is not None:
            if existing.node is not None and existing.node.ref != node.ref:
                # print("  +++++Runtime conflict!", require, "with", node.ref)
                return True

        self.transitive_deps.set(require, TransitiveRequirement(require, node))

        if not self.dependants:
            # print("  No further dependants, stop propagate")
            return

        if prev_node:
            d = [d for d in self.dependants if d.src is prev_node][0]  # TODO: improve ugly
        else:
            assert len(self.dependants) == 1
            d = self.dependants[0]

        downstream_require = self._transform_downstream_require(require, node, d)

        # Check if need to propagate downstream
        if downstream_require is None:
            # print("  No downstream require, stopping propagate")
            return

        return d.src.propagate_downstream(downstream_require, node)

    def check_downstream_exists(self, require):
        # First, a check against self, could be a loop-conflict
        # This is equivalent as the Requirement hash and eq methods
        # TODO: Make self.ref always exist, but with name=None if name not defined
        if self.ref is not None and require.ref.name == self.ref.name:
            return None, self, self  # First is the require, as it is a loop => None

        # First do a check against the current node dependencies
        prev = self.transitive_deps.get(require)
        # print("    Transitive deps", self.transitive_deps)
        # ("    THERE IS A PREV ", prev, "in node ", self, " for require ", require)
        # Overrides: The existing require could be itself, that was just added
        if prev and (prev.require is not require or prev.node is not None):
            return prev.require, prev.node, self

        # Check if need to propagate downstream
        # Then propagate downstream

        # Seems the algrithm depth-first, would only have 1 dependant at most to propagate down
        # at any given time
        if not self.dependants:
            return
        assert len(self.dependants) == 1
        d = self.dependants[0]

        # TODO: Implement an optimization where the requires is checked against a graph global
        # print("    Lets check_downstream one more")
        downstream_require = self._transform_downstream_require(require, None, d)
        if downstream_require is None:
            # print("    No need to check dowstream more")
            return

        source_node = d.src
        return source_node.check_downstream_exists(downstream_require)

    @property
    def package_id(self):
        return self._package_id

    @package_id.setter
    def package_id(self, pkg_id):
        assert self._package_id is None, "Trying to override an existing package_id"
        self._package_id = pkg_id

    @property
    def name(self):
        return self.ref.name if self.ref else None

    @property
    def pref(self):
        assert self.ref is not None and self.package_id is not None, "Node %s" % self.recipe
        return PackageReference(self.ref, self.package_id, self.prev)

    def add_edge(self, edge):
        if edge.src == self:
            if edge not in self.dependencies:
                self.dependencies.append(edge)
        else:
            self.dependants.append(edge)

    def neighbors(self):
        return [edge.dst for edge in self.dependencies]

    def private_neighbors(self):
        return [edge.dst for edge in self.dependencies if edge.private]

    def inverse_neighbors(self):
        return [edge.src for edge in self.dependants]

    def __repr__(self):
        return repr(self.conanfile)


class Edge(object):
    def __init__(self, src, dst, require):
        self.src = src
        self.dst = dst
        self.require = require
        # FIXME: USed in the ConanFileDependencies logic, must avoid
        self.build_require = False  # Just to not break, but not user
        self.private = False


class DepsGraph(object):
    def __init__(self, initial_node_id=None):
        self.nodes = []
        self.aliased = {}
        self.error = False
        self._node_counter = initial_node_id if initial_node_id is not None else -1

    def __repr__(self):
        return "\n".join((repr(n) for n in self.nodes))

    @property
    def root(self):
        return self.nodes[0] if self.nodes else None

    def add_node(self, node):
        if node.id is None:
            self._node_counter += 1
            node.id = str(self._node_counter)
        self.nodes.append(node)

    def add_edge(self, src, dst, require):
        assert src in self.nodes and dst in self.nodes
        edge = Edge(src, dst, require)
        src.add_edge(edge)
        dst.add_edge(edge)

    def ordered_iterate(self, nodes_subset=None):
        ordered = self.by_levels(nodes_subset)
        for level in ordered:
            for node in level:
                yield node

    def nodes_to_build(self):
        ret = []
        for node in self.ordered_iterate():
            if node.binary == BINARY_BUILD:
                if node.ref.copy_clear_rev() not in ret:
                    ret.append(node.ref.copy_clear_rev())
        return ret

    def by_levels(self, nodes_subset=None):
        return self._order_levels(True, nodes_subset)

    def inverse_levels(self):
        return self._order_levels(False)

    def _order_levels(self, direct, nodes_subset=None):
        """ order by node degree. The first level will be the one which nodes dont have
        dependencies. Second level will be with nodes that only have dependencies to
        first level nodes, and so on
        return [[node1, node34], [node3], [node23, node8],...]
        """
        result = []
        opened = nodes_subset if nodes_subset is not None else set(self.nodes)
        while opened:
            current_level = []
            for o in opened:
                o_neighs = o.neighbors() if direct else o.inverse_neighbors()
                if not any(n in opened for n in o_neighs):
                    current_level.append(o)

            # TODO: SORTING seems only necessary for test order
            current_level.sort()
            result.append(current_level)
            # now initialize new level
            opened = opened.difference(current_level)

        return result

    def mark_private_skippable(self, nodes_subset=None, root=None):
        """ check which nodes are reachable from the root, mark the non reachable as BINARY_SKIP.
        Used in the GraphBinaryAnalyzer"""
        public_nodes = set()
        root = root if root is not None else self.root
        nodes = nodes_subset if nodes_subset is not None else self.nodes
        current = [root]
        while current:
            new_current = set()
            public_nodes.update(current)
            for n in current:
                if n.binary in (BINARY_CACHE, BINARY_DOWNLOAD, BINARY_UPDATE, BINARY_SKIP):
                    # Might skip deps
                    to_add = [d.dst for d in n.dependencies if not d.private]
                else:
                    # sure deps doesn't skip
                    to_add = set(n.neighbors()).difference(public_nodes)
                new_current.update(to_add)
            current = new_current

        for node in nodes:
            if node not in public_nodes:
                node.binary_non_skip = node.binary
                node.binary = BINARY_SKIP

    def build_time_nodes(self):
        """ return all the nodes in the graph that are build-requires (either directly or
        transitively). Nodes that are both in requires and build_requires will not be returned.
        This is used just for output purposes, printing deps, HTML graph, etc.
        """
        return [n for n in self.nodes if n.context == CONTEXT_BUILD]

    def report_graph_error(self):
        if self.error:
            raise self.error
