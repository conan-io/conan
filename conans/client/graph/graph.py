from conans.model.ref import PackageReference
from conans.model.info import ConanInfo
from conans.errors import conanfile_exception_formatter


class Node(object):
    def __init__(self, conan_ref, conanfile):
        self.conan_ref = conan_ref
        self.conanfile = conanfile
        self.dependencies = set()  # Edges
        self.dependants = set()  # Edges

    def add_edge(self, edge):
        if edge.src == self:
            self.dependencies.add(edge)
        else:
            self.dependants.add(edge)

    def neighbors(self):
        return set(edge.dst for edge in self.dependencies)

    def public_neighbors(self):
        return set(edge.dst for edge in self.dependencies if not edge.private)

    def inverse_neighbors(self):
        return set(edge.src for edge in self.dependants)

    def __eq__(self, other):
        return (self.conan_ref == other.conan_ref and
                self.conanfile == other.conanfile)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.conan_ref, self.conanfile))

    def __repr__(self):
        return repr(self.conanfile)

    def __cmp__(self, other):
        if other is None:
            return -1
        elif self.conan_ref is None:
            return 0 if other.conan_ref is None else -1
        elif other.conan_ref is None:
            return 1

        if self.conan_ref == other.conan_ref:
            return 0
        if self.conan_ref < other.conan_ref:
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
    def __init__(self, src, dst, private=False):
        self.src = src
        self.dst = dst
        self.private = private

    def __eq__(self, other):
        return self.src == self.src and self.dst == other.dst

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.src, self.dst))


class DepsGraph(object):
    def __init__(self):
        self.nodes = set()

    def add_node(self, node):
        self.nodes.add(node)

    def add_edge(self, src, dst, private=False):
        assert src in self.nodes and dst in self.nodes
        edge = Edge(src, dst, private)
        src.add_edge(edge)
        dst.add_edge(edge)

    def propagate_info(self):
        """ takes the exports from upper level and updates the imports
        right now also the imports are propagated, but should be checked
        E.g. Conan A, depends on B.  A=>B
        B exports an include directory "my_dir", with root "/...../0123efe"
        A imports are the exports of B, plus any other conans it depends on
        A.imports.include_dirs = B.export.include_paths.
        Note the difference, include_paths used to compute full paths as the user
        defines export relative to its folder
        """
        ordered = self.by_levels()
        for level in ordered:
            for node in level:
                conanfile = node.conanfile
                neighbors = node.neighbors()
                direct_reqs = []  # of PackageReference
                indirect_reqs = set()   # of PackageReference, avoid duplicates
                for neighbor in neighbors:
                    nref, nconan = neighbor.conan_ref, neighbor.conanfile
                    package_id = nconan.info.package_id()
                    package_reference = PackageReference(nref, package_id)
                    direct_reqs.append(package_reference)
                    indirect_reqs.update(nconan.info.requires.refs())
                    conanfile.options.propagate_downstream(nref, nconan.info.full_options)
                    # Might be never used, but update original requirement, just in case
                    conanfile.requires[nref.name].conan_reference = nref

                # Make sure not duplicated
                indirect_reqs.difference_update(direct_reqs)
                # There might be options that are not upstream, backup them, might be
                # for build-requires
                conanfile.build_requires_options = conanfile.options.values
                conanfile.options.clear_unused(indirect_reqs.union(direct_reqs))

                conanfile.info = ConanInfo.create(conanfile.settings.values,
                                                  conanfile.options.values,
                                                  direct_reqs,
                                                  indirect_reqs)

                # Once we are done, call package_id() to narrow and change possible values
                with conanfile_exception_formatter(str(conanfile), "package_id"):
                    conanfile.package_id()
        return ordered

    def direct_requires(self):
        nodes_by_level = self.inverse_levels()
        open_nodes = nodes_by_level[1]
        return open_nodes

    def ordered_closure(self, node, flat):
        closure = set()
        current = node.neighbors()
        while current:
            new_current = set()
            for n in current:
                closure.add(n)
                new_neighs = n.public_neighbors()
                to_add = set(new_neighs).difference(current)
                new_current.update(to_add)
            current = new_current

        result = [n for n in flat if n in closure]
        return result

    def public_closure(self, node):
        closure = {}
        current = node.neighbors()
        while current:
            new_current = set()
            for n in current:
                closure[n.conan_ref.name] = n
                new_neighs = n.public_neighbors()
                to_add = set(new_neighs).difference(current)
                new_current.update(to_add)
            current = new_current

        return closure

    def _inverse_closure(self, references):
        closure = set()
        current = [n for n in self.nodes if str(n.conan_ref) in references or "ALL" in references]
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

    def build_order(self, references):
        levels = self.inverse_levels()
        closure = self._inverse_closure(references)
        result = []
        for level in reversed(levels):
            new_level = [n.conan_ref for n in level if (n in closure and n.conan_ref)]
            if new_level:
                result.append(new_level)
        return result

    def by_levels(self):
        return self._order_levels(True)

    def inverse_levels(self):
        return self._order_levels(False)

    def _order_levels(self, direct):
        """ order by node degree. The first level will be the one which nodes dont have
        dependencies. Second level will be with nodes that only have dependencies to
        first level nodes, and so on
        return [[node1, node34], [node3], [node23, node8],...]
        """
        current_level = []
        result = [current_level]
        opened = self.nodes.copy()
        while opened:
            current = opened.copy()
            for o in opened:
                o_neighs = o.neighbors() if direct else o.inverse_neighbors()
                if not any(n in opened for n in o_neighs):
                    current_level.append(o)
                    current.discard(o)
            current_level.sort()
            # now initialize new level
            opened = current
            if opened:
                current_level = []
                result.append(current_level)

        return result

    def private_nodes(self, built_private_nodes):
        """ computes a list of nodes living in the private zone of the deps graph,
        together with the list of nodes that privately require it
        """
        closure = set()
        nodes_by_level = self.by_levels()
        open_nodes = nodes_by_level[-1]
        closure.update(open_nodes)
        while open_nodes:
            new_open_nodes = set()
            for node in open_nodes:
                if node in built_private_nodes:
                    neighbors = node.public_neighbors()
                else:
                    neighbors = node.neighbors()
                new_open_nodes.update(set(neighbors).difference(closure))
                closure.update(neighbors)
            open_nodes = new_open_nodes

        private_nodes = self.nodes.difference(closure)
        result = []
        for node in private_nodes:
            result.append(node)
        return result
