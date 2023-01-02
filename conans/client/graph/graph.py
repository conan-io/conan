from collections import OrderedDict

from conans.model.package_ref import PkgReference

RECIPE_DOWNLOADED = "Downloaded"
RECIPE_INCACHE = "Cache"  # The previously installed recipe in cache is being used
RECIPE_UPDATED = "Updated"
RECIPE_INCACHE_DATE_UPDATED = "Cache (Updated date)"
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
BINARY_EDITABLE_BUILD = "EditableBuild"
BINARY_INVALID = "Invalid"

CONTEXT_HOST = "host"
CONTEXT_BUILD = "build"


class TransitiveRequirement:
    def __init__(self, require, node):
        self.require = require
        self.node = node

    def __repr__(self):
        return "Require: {}, Node: {}".format(repr(self.require), repr(self.node))


class Node(object):
    def __init__(self, ref, conanfile, context, recipe=None, path=None, test=False):
        self.ref = ref
        self.path = path  # path to the consumer conanfile.xx for consumer, None otherwise
        self._package_id = None
        self.prev = None
        self.pref_timestamp = None
        if conanfile is not None:
            conanfile._conan_node = self  # Reference to self, to access data
        self.conanfile = conanfile

        self.binary = None
        self.recipe = recipe
        self.remote = None
        self.binary_remote = None
        self.context = context
        self.test = test

        # real graph model
        self.transitive_deps = OrderedDict()  # of _TransitiveRequirement
        self.dependencies = []  # Ordered Edges
        self.dependants = []  # Edges
        self.error = None
        self.cant_build = False  # It will set to a str with a reason if the validate_build() fails
        self.should_build = False  # If the --build or policy wants to build this binary

    def __lt__(self, other):
        """
        @type other: Node
        """
        # TODO: Remove this order, shouldn't be necessary
        return (str(self.ref), self._package_id) < (str(other.ref), other._package_id)

    def propagate_closing_loop(self, require, prev_node):
        self.propagate_downstream(require, prev_node)
        # List to avoid mutating the dict
        for transitive in list(prev_node.transitive_deps.values()):
            # TODO: possibly optimize in a bulk propagate
            prev_node.propagate_downstream(transitive.require, transitive.node, self)

    def propagate_downstream(self, require, node, src_node=None):
        # print("  Propagating downstream ", self, "<-", require)
        assert node is not None
        # This sets the transitive_deps node if it was None (overrides)
        # Take into account that while propagating we can find RUNTIME shared conflicts we
        # didn't find at check_downstream_exist, because we didn't know the shared/static
        existing = self.transitive_deps.get(require)
        if existing is not None and existing.require is not require:
            if existing.node is not None and existing.node.ref != node.ref:
                # print("  +++++Runtime conflict!", require, "with", node.ref)
                return True
            require.aggregate(existing.require)

        # TODO: Might need to move to an update() for performance
        self.transitive_deps.pop(require, None)
        self.transitive_deps[require] = TransitiveRequirement(require, node)

        # Check if need to propagate downstream
        if not self.dependants:
            return

        if src_node is not None:  # This happens when closing a loop, and we need to know the edge
            d = [d for d in self.dependants if d.src is src_node][0]  # TODO: improve ugly
        else:
            assert len(self.dependants) == 1
            d = self.dependants[0]

        down_require = d.require.transform_downstream(self.conanfile.package_type, require,
                                                      node.conanfile.package_type)
        if down_require is None:
            return

        return d.src.propagate_downstream(down_require, node)

    def check_downstream_exists(self, require):
        # First, a check against self, could be a loop-conflict
        # This is equivalent as the Requirement hash and eq methods
        # TODO: Make self.ref always exist, but with name=None if name not defined
        if self.ref is not None and require.ref.name == self.ref.name:
            if require.build and (self.context == CONTEXT_HOST or  # switch context
                                  require.ref.version != self.ref.version):  # or different version
                pass
            else:
                return None, self, self  # First is the require, as it is a loop => None

        # First do a check against the current node dependencies
        prev = self.transitive_deps.get(require)
        # print("    Transitive deps", self.transitive_deps)
        # ("    THERE IS A PREV ", prev, "in node ", self, " for require ", require)
        # Overrides: The existing require could be itself, that was just added
        result = None
        if prev and (prev.require is not require or prev.node is not None):
            result = prev.require, prev.node, self
            # Do not return yet, keep checking downstream, because downstream overrides or forces
            # have priority

        # Check if need to propagate downstream
        # Then propagate downstream

        # Seems the algrithm depth-first, would only have 1 dependant at most to propagate down
        # at any given time
        if not self.dependants:
            return result
        assert len(self.dependants) == 1
        dependant = self.dependants[0]

        # TODO: Implement an optimization where the requires is checked against a graph global
        # print("    Lets check_downstream one more")
        down_require = dependant.require.transform_downstream(self.conanfile.package_type,
                                                              require, None)

        if down_require is None:
            # print("    No need to check downstream more")
            return result

        source_node = dependant.src
        return source_node.check_downstream_exists(down_require) or result

    def check_loops(self, new_node):
        if self.ref == new_node.ref and self.context == new_node.context:
            return self
        if not self.dependants:
            return
        assert len(self.dependants) == 1
        dependant = self.dependants[0]
        source_node = dependant.src
        return source_node.check_loops(new_node)

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
        return PkgReference(self.ref, self.package_id, self.prev, self.pref_timestamp)

    def add_edge(self, edge):
        if edge.src == self:
            assert edge not in self.dependencies
            self.dependencies.append(edge)
        else:
            self.dependants.append(edge)

    def neighbors(self):
        return [edge.dst for edge in self.dependencies]

    def inverse_neighbors(self):
        return [edge.src for edge in self.dependants]

    def __repr__(self):
        return repr(self.conanfile)

    def serialize(self):
        result = OrderedDict()
        result["ref"] = self.ref.repr_notime() if self.ref is not None else "conanfile"
        result["id"] = getattr(self, "id")  # Must be assigned by graph.serialize()
        result["recipe"] = self.recipe
        result["package_id"] = self.package_id
        result["prev"] = self.prev
        from conans.client.installer import build_id
        result["build_id"] = build_id(self.conanfile)
        result["binary"] = self.binary
        # TODO: This doesn't match the model, check it
        result["invalid_build"] = self.cant_build is not False
        if self.cant_build:
            result["invalid_build_reason"] = self.cant_build
        # Adding the conanfile information: settings, options, etc
        result.update(self.conanfile.serialize())
        result["context"] = self.context
        result["test"] = self.test
        result["requires"] = {n.id: n.ref.repr_notime() for n in self.neighbors()}
        return result


class Edge(object):
    def __init__(self, src, dst, require):
        self.src = src
        self.dst = dst
        self.require = require


class DepsGraph(object):
    def __init__(self):
        self.nodes = []
        self.aliased = {}
        self.resolved_ranges = {}
        self.error = False

    def __repr__(self):
        return "\n".join((repr(n) for n in self.nodes))

    @property
    def root(self):
        return self.nodes[0] if self.nodes else None

    def add_node(self, node):
        self.nodes.append(node)

    def add_edge(self, src, dst, require):
        assert src in self.nodes and dst in self.nodes
        edge = Edge(src, dst, require)
        src.add_edge(edge)
        dst.add_edge(edge)

    def ordered_iterate(self):
        ordered = self.by_levels()
        for level in ordered:
            for node in level:
                yield node

    def by_levels(self):
        """ order by node degree. The first level will be the one which nodes dont have
        dependencies. Second level will be with nodes that only have dependencies to
        first level nodes, and so on
        return [[node1, node34], [node3], [node23, node8],...]
        """
        result = []
        # We make it a dict to preserve insertion order and be deterministic, s
        # sets are not deterministic order. dict is fast for look up operations
        opened = dict.fromkeys(self.nodes)
        while opened:
            current_level = []
            for o in opened:
                o_neighs = o.neighbors()
                if not any(n in opened for n in o_neighs):
                    current_level.append(o)

            # TODO: SORTING seems only necessary for test order
            current_level.sort()
            result.append(current_level)
            # now start new level, removing the current level items
            for item in current_level:
                opened.pop(item)

        return result

    def build_time_nodes(self):
        """ return all the nodes in the graph that are build-requires (either directly or
        transitively). Nodes that are both in requires and build_requires will not be returned.
        This is used just for output purposes, printing deps, HTML graph, etc.
        """
        return [n for n in self.nodes if n.context == CONTEXT_BUILD]

    def report_graph_error(self):
        if self.error:
            raise self.error

    def serialize(self):
        for i, n in enumerate(self.nodes):
            n.id = i
        result = OrderedDict()
        result["nodes"] = [n.serialize() for n in self.nodes]
        result["root"] = {self.root.id: repr(self.root.ref)}  # TODO: ref of consumer/virtual
        return result
