from collections import OrderedDict

from conans.model.ref import PackageReference
from conans.model.requires import Requirement

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


class _PackageRelation:
    def __init__(self, ref):
        self.ref = ref

    def transform_downstream(self, node):
        assert node
        return _PackageRelation(self.ref)

    def __hash__(self):
        return hash(self.ref.name)

    def __eq__(self, other):
        return self.ref.name == other.ref.name

    def __ne__(self, other):
        return not self.__eq__(other)


class _TransitivePackages:
    def __init__(self):
        # The PackageRelation hash function is the key here
        self._relations = OrderedDict()  # {require: Node}

    def get(self, relation):
        return self._relations.get(relation)

    def set(self, relation, node):
        self._relations[relation] = node

    def items(self):
        return self._relations.items()


class Node(object):
    def __init__(self, ref, conanfile, context, recipe=None, path=None):
        self.ref = ref
        self.path = path  # path to the consumer conanfile.xx for consumer, None otherwise
        self._package_id = None
        self.prev = None
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
        self.transitive_deps = _TransitivePackages()
        self.dependencies = []  # Ordered Edges
        self.dependants = []  # Edges
        self.conflict = None

    def __lt__(self, other):
        # TODO: Remove this order, shouldn't be necessary
        return id(self) < id(other)

    def propagate_downstream(self, relation, node):
        if not isinstance(relation, _PackageRelation):
            assert isinstance(relation, Requirement)
            relation = _PackageRelation(relation.ref)

        self.transitive_deps.set(relation, node)
        return self.propagate_downstream_existing(relation, node)

    def propagate_downstream_existing(self, relation, node):
        # Check if need to propagate downstream
        downstream_relation = relation.transform_downstream(self)
        if downstream_relation is None:
            return

        if not self.dependants:
            return
        assert len(self.dependants) == 1
        d = self.dependants[0]
        source_node = d.src
        return source_node.propagate_downstream(downstream_relation, node)

    def check_downstream_exists(self, relation):
        if not isinstance(relation, _PackageRelation):
            assert isinstance(relation, Requirement)
            relation = _PackageRelation(relation.ref)
        # First, a check against self, could be a loop-conflict
        # This is equivalent as the _PackageRelation hash and eq methods
        # TODO: Make self.ref always exist, but with name=None if name not defined
        if self.ref is not None and relation.ref.name == self.ref.name:
            return self, self

        # First do a check against the current node dependencies
        prev = self.transitive_deps.get(relation)
        if prev:
            return prev, self

        # Check if need to propagate downstream
        downstream_relation = relation.transform_downstream(self)
        if downstream_relation is None:
            return

        # Then propagate downstream
        # TODO: Implement an optimization where the requires is checked against a graph global
        # Seems the algrithm depth-first, would only have 1 dependant at most to propagate down
        # at any given time
        if not self.dependants:
            return
        assert len(self.dependants) == 1
        d = self.dependants[0]
        source_node = d.src
        return source_node.check_downstream_exists(downstream_relation)

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
        self.build_require = False  # Just to not break, but not user
        self.private = False


class DepsGraph(object):
    def __init__(self, initial_node_id=None):
        self.nodes = []
        self.aliased = {}
        self.conflict = False
        self._node_counter = initial_node_id if initial_node_id is not None else -1

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

            # TODO: SORTING NOT NECESSARY NOW current_level.sort()
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
        public_nodes = set()
        current = [self.root]
        while current:
            new_current = set()
            public_nodes.update(current)
            for n in current:
                # Might skip deps
                to_add = [d.dst for d in n.dependencies if not d.build_require]
                new_current.update(to_add)
            current = new_current

        return [n for n in self.nodes if n not in public_nodes]
