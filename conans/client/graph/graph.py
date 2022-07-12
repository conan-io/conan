from collections import OrderedDict

from conans.model.ref import PackageReference

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


class _NodeOrderedDict(object):

    def __init__(self):
        self._nodes = OrderedDict()

    @staticmethod
    def _key(node):
        return node.name, node.context

    def add(self, node):
        key = self._key(node)
        self._nodes[key] = node

    def get(self, name, context):
        return self._nodes.get((name, context))

    def pop(self, name, context):
        return self._nodes.pop((name, context))

    def sort(self, key_fn):
        sorted_nodes = sorted(self._nodes.items(), key=lambda n: key_fn(n[1]))
        self._nodes = OrderedDict(sorted_nodes)

    def assign(self, other):
        assert isinstance(other, _NodeOrderedDict), "Unexpected type: {}".format(type(other))
        self._nodes = other._nodes.copy()

    def __iter__(self):
        for _, item in self._nodes.items():
            yield item


class Node(object):
    def __init__(self, ref, conanfile, context, recipe=None, path=None):
        self.ref = ref
        self.path = path  # path to the consumer conanfile.xx for consumer, None otherwise
        self._package_id = None
        self.prev = None
        conanfile._conan_node = self  # Reference to self, to access data
        self.conanfile = conanfile
        self.dependencies = []  # Ordered Edges
        self.dependants = set()  # Edges
        self.binary = None
        self.recipe = recipe
        self.remote = None
        self.binary_remote = None
        self.revision_pinned = False  # The revision has been specified by the user
        self.context = context

        # A subset of the graph that will conflict by package name
        self._public_deps = _NodeOrderedDict()  # {ref.name: Node}
        # all the public deps only in the closure of this node
        # The dependencies that will be part of deps_cpp_info, can't conflict
        self._public_closure = _NodeOrderedDict()  # {ref.name: Node}
        # The dependencies of this node that will be propagated to consumers when they depend
        # on this node. It includes regular (not private and not build requires) dependencies
        self._transitive_closure = OrderedDict()
        self.inverse_closure = set()  # set of nodes that have this one in their public
        self._ancestors = _NodeOrderedDict()  # set{ref.name}
        self._id = None  # Unique ID (uuid at the moment) of a node in the graph
        self.graph_lock_node = None  # the locking information can be None
        self.id_direct_prefs = None
        self.id_indirect_prefs = None

        self.cant_build = False  # It will set to a str with a reason if the validate_build() fails

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, id_):
        self._id = id_

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

    @property
    def public_deps(self):
        return self._public_deps

    @property
    def public_closure(self):
        return self._public_closure

    @property
    def transitive_closure(self):
        return self._transitive_closure

    @property
    def ancestors(self):
        return self._ancestors

    def partial_copy(self):
        # Used for collapse_graph
        result = Node(self.ref, self.conanfile, self.context, self.recipe, self.path)
        result.dependants = set()
        result.dependencies = []
        result.binary = self.binary
        result.remote = self.remote
        result.binary_remote = self.binary_remote
        return result

    def add_edge(self, edge):
        if edge.src == self:
            if edge not in self.dependencies:
                self.dependencies.append(edge)
        else:
            self.dependants.add(edge)

    def neighbors(self):
        return [edge.dst for edge in self.dependencies]

    def private_neighbors(self):
        return [edge.dst for edge in self.dependencies if edge.private]

    def connect_closure(self, other_node):
        # When 2 nodes of the graph become connected, their closures information has
        # has to remain consistent. This method manages this.
        self.public_closure.add(other_node)
        self.public_deps.add(other_node)
        other_node.inverse_closure.add(self)

    def inverse_neighbors(self):
        return [edge.src for edge in self.dependants]

    def __eq__(self, other):
        return (self.ref == other.ref and
                self.conanfile == other.conanfile and
                self.context == other.context)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.ref, self.conanfile, self.context))

    def __repr__(self):
        return repr(self.conanfile)

    def __cmp__(self, other):
        if other is None:
            return -1
        elif self.ref is None:
            return 0 if other.ref is None else -1
        elif other.ref is None:
            return 1

        if self.ref == other.ref:
            return 0

        # Cannot compare None with str
        if self.ref.revision is None and other.ref.revision is not None:
            return 1

        if self.ref.revision is not None and other.ref.revision is None:
            return -1

        if self.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
            return 1
        if other.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
            return -1
        if self.ref < other.ref:
            return -1

        return 1

    def __gt__(self, other):
        return self.__cmp__(other) == 1

    def __lt__(self, other):
        return self.__cmp__(other) == -1

    def __le__(self, other):
        return self.__cmp__(other) in [0, -1]

    def __ge__(self, other):
        return self.__cmp__(other) in [0, 1]


class Edge(object):
    def __init__(self, src, dst, require):
        self.src = src
        self.dst = dst
        self.require = require

    @property
    def private(self):
        return self.require.private

    @property
    def build_require(self):
        return self.require.build_require

    def __eq__(self, other):
        return self.src == self.src and self.dst == other.dst

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.src, self.dst))


class DepsGraph(object):
    def __init__(self, initial_node_id=None):
        self.nodes = set()
        self.root = None
        self.aliased = {}
        self.new_aliased = {}
        self._node_counter = initial_node_id if initial_node_id is not None else -1

    def add_node(self, node):
        if node.id is None:
            self._node_counter += 1
            node.id = str(self._node_counter)
        if not self.nodes:
            self.root = node
        self.nodes.add(node)

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

    def _inverse_closure(self, references):
        closure = set()
        current = [n for n in self.nodes if str(n.ref) in references or "ALL" in references]
        closure.update(current)
        while current:
            new_current = set()
            for n in current:
                closure.add(n)
                new_neighs = n.inverse_neighbors()
                to_add = set(new_neighs).difference(current)
                new_current.update(to_add)
            current = new_current
        return closure

    def collapse_graph(self):
        """Computes and return a new graph, that doesn't have duplicated nodes with the same
        PackageReference. This is the case for build_requires and private requirements
        """
        result = DepsGraph()
        result.add_node(self.root.partial_copy())
        unique_nodes = {}  # {PackageReference: Node (result, unique)}
        nodes_map = {self.root: result.root}  # {Origin Node: Result Node}
        # Add the nodes, without repetition. THe "node.partial_copy()" copies the nodes
        # without Edges
        for node in self.nodes:
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
                continue
            pref = PackageReference(node.ref, node.package_id)
            if pref not in unique_nodes:
                result_node = node.partial_copy()
                result.add_node(result_node)
                unique_nodes[pref] = result_node
            else:
                result_node = unique_nodes[pref]
            nodes_map[node] = result_node

        # Compute the new edges of the graph
        for node in self.nodes:
            result_node = nodes_map[node]
            for dep in node.dependencies:
                src = result_node
                dst = nodes_map[dep.dst]
                result.add_edge(src, dst, dep.require)
            for dep in node.dependants:
                src = nodes_map[dep.src]
                dst = result_node
                result.add_edge(src, dst, dep.require)

        return result

    def build_order(self, references):
        new_graph = self.collapse_graph()
        levels = new_graph.inverse_levels()
        closure = new_graph._inverse_closure(references)
        result = []
        for level in reversed(levels):
            new_level = [n.ref for n in level
                         if (n in closure and n.recipe not in (RECIPE_CONSUMER, RECIPE_VIRTUAL))]
            if new_level:
                result.append(new_level)
        return result

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
        opened = nodes_subset if nodes_subset is not None else self.nodes
        while opened:
            current_level = []
            for o in opened:
                o_neighs = o.neighbors() if direct else o.inverse_neighbors()
                if not any(n in opened for n in o_neighs):
                    current_level.append(o)

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
