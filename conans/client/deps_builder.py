""" This module is responsible for computing the dependencies (graph) for a given entry
point, which could be both a user conanfile or an installed one
"""
from conans.model.requires import Requirements
from collections import namedtuple
from conans.model.ref import PackageReference
from conans.model.build_info import DepsCppInfo
from conans.model.info import ConanInfo
from conans.errors import ConanException
from conans.client.output import ScopedOutput


class Edge(namedtuple("Edge", "src dst")):
    """ Simple edge of the dependencies graph src=>dst
    """
    def __repr__(self):
        return ("%s => %s IDs: %s => %s"
                % (repr(self.src.conan_ref), repr(self.dst.conan_ref),
                   str(id(self.src)), str(id(self.dst))))


class Node(namedtuple("Node", "conan_ref conanfile")):
    """ The Node of the dependencies graph is defined by:
    ref: ConanFileReference, if it is a user space one, user=channel=none
    conanfile: the loaded conanfile object withs its values
    """
    def __repr__(self):
        return "%s => %s" % (repr(self.conan_ref), repr(self.conanfile)[:100].replace("\n", " "))


class DepsGraph(object):
    """ DAG of dependencies
    """
    def __init__(self):
        self.nodes = set()
        self.edges = set()

    def get_nodes(self, name):
        """ return all the nodes matching a particular name. Could be >1 in case
        that private requirements embed different versions
        """
        return [n for n in self.nodes if n.conanfile.name == name]

    def add_node(self, node):
        self.nodes.add(node)

    def add_edge(self, src, dst):
        assert src in self.nodes and dst in self.nodes
        self.edges.add(Edge(src, dst))

    def neighbors(self, node):
        """ return all connected nodes (directionally) to the parameter one
        """
        return [edge.dst for edge in self.edges if edge.src == node]

    def inverse_neighbors(self, node):
        """ return all the nodes which has param node has dependency
        """
        return [edge.src for edge in self.edges if edge.dst == node]

    def public_neighbors(self, node):
        """ return nodes with direct reacheability by public dependencies
        """
        neighbors = self.neighbors(node)
        result = []
        _, conanfile = node
        for n in neighbors:
            for req in conanfile.requires.itervalues():
                if req.conan_reference == n.conan_ref:
                    if not req.private:
                        result.append(n)
        return result

    def private_inverse_neighbors(self, node):
        """ return nodes connected to a given one (inversely), by a private requirement
        """
        neighbors = self.inverse_neighbors(node)
        result = []
        for n in neighbors:
            _, conanfile = n
            for req in conanfile.requires.itervalues():
                if req.conan_reference == node.conan_ref:
                    if req.private:
                        result.append(n)
        return result

    def __repr__(self):
        return "\n".join(["Nodes:\n    ",
                          "\n    ".join(repr(n) for n in self.nodes),
                          "\nEdges:\n    ",
                          "\n    ".join(repr(n) for n in self.edges)])

    def propagate_buildinfo(self):
        """ takes the exports from upper level and updates the imports
        right now also the imports are propagated, but should be checked
        E.g. Conan A, depends on B.  A=>B
        B exports an include directory "my_dir", with root "/...../0123efe"
        A imports are the exports of B, plus any other conans it depends on
        A.imports.include_dirs = B.export.include_paths.
        Note the difference, include_paths used to compute full paths as the user
        defines export relative to its folder
        """
        # Temporary field to store the transitive build info to account for
        # private requirements
        for node in self.nodes:
            node.conanfile.transitive_buildinfo = DepsCppInfo()

        # To propagate, this should be done in top-down order
        ordered = self.by_levels()
        for level in ordered[1:]:
            for node in level:
                _, conanfile = node
                neighbors = self.neighbors(node)
                public_neighbors = self.public_neighbors(node)
                # Compute transitive build_info
                for n in public_neighbors:
                    conanfile.transitive_buildinfo.update(n.conanfile.cpp_info, n.conan_ref)
                    conanfile.transitive_buildinfo.update(n.conanfile.transitive_buildinfo)

                # propagate first (order is important), the export_buildinfo
                for n in neighbors:
                    conanfile.deps_cpp_info.update(n.conanfile.cpp_info,
                                                   n.conan_ref)

                for n in neighbors:
                    # FIXME: Check this imports propagation, wrong for deep hierarchies
                    conanfile.deps_cpp_info.update(n.conanfile.transitive_buildinfo)
        return ordered

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
                _, conanfile = node
                neighbors = self.neighbors(node)
                direct_reqs = []  # of PackageReference
                indirect_reqs = set()   # of PackageReference, avoid duplicates
                for nref, nconan in neighbors:
                    package_id = nconan.info.package_id()
                    package_reference = PackageReference(nref, package_id)
                    direct_reqs.append(package_reference)
                    indirect_reqs.update(nconan.info.requires.refs())
                    conanfile.options.propagate_downstream(nref, nconan.info.full_options)
                    # Might be never used, but update original requirement, just in case
                    conanfile.requires[nref.name].conan_reference = nref
                # There might be options that are not upstream
                conanfile.options.clear_unused(indirect_reqs.union(direct_reqs))

                conanfile.info = ConanInfo.create(conanfile.settings.values,
                                                  conanfile.options.values,
                                                  direct_reqs)
                conanfile.info.requires.add(indirect_reqs)
                conanfile.info.full_requires.extend(indirect_reqs)

                # Once we are done, call conan_info() to narrow and change possible values
                conanfile.conan_info()
        return ordered

    def by_levels(self):
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
                if not any(o == edge.src and edge.dst in opened for edge in self.edges):
                    current_level.append(o)
                    current.discard(o)
            current_level.sort()
            # now initialize new level
            opened = current
            if opened:
                current_level = []
                result.append(current_level)
        return result

    def private_nodes(self):
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
                neighbors = self.public_neighbors(node)
                new_open_nodes.update(set(neighbors).difference(closure))
                closure.update(neighbors)
            open_nodes = new_open_nodes

        private_nodes = self.nodes.difference(closure)
        result = []
        for node in private_nodes:
            result.append((node, self.private_inverse_neighbors(node)))
        return result


class DepsBuilder(object):
    """ Responsible for computing the dependencies graph DepsGraph
    """
    def __init__(self, retriever, output, loader):
        """ param retriever: something that implements retrieve_conanfile for installed conans
        param loader: helper ConanLoader to be able to load user space conanfile
        """
        self._retriever = retriever
        self._output = output
        self._loader = loader

    def get_graph_updates_info(self, deps_graph):
        """
        returns a dict of conan_reference: 1 if there is an update, 0 if don't and -1 if local is newer
        """
        return {conan_reference: self._retriever.update_available(conan_reference)
                for conan_reference, _ in deps_graph.nodes}

    def load(self, conan_ref, conanfile):
        """ compute the dependencies graph for:
        param conan_ref: ConanFileReference for installed conanfile or path to user one
                         might be None for user conanfile.py or .txt
        """
        dep_graph = DepsGraph()
        # compute the conanfile entry point for this dependency graph
        root_node = Node(conan_ref, conanfile)
        dep_graph.add_node(root_node)
        public_deps = {}  # {name: Node} dict with public nodes, so they are not added again
        # enter recursive computation
        self._load_deps(root_node, Requirements(), dep_graph, public_deps, conan_ref, None)
        dep_graph.propagate_info()
        return dep_graph

    def _load_deps(self, node, down_reqs, dep_graph, public_deps, down_ref, down_options):
        """ loads a Conan object from the given file
        param node: Node object to be expanded in this step
        down_reqs: the Requirements as coming from downstream, which can overwrite current
                    values
        param settings: dict of settings values => {"os": "windows"}
        param deps: DepsGraph result
        param public_deps: {name: Node} of already expanded public Nodes, not to be repeated
                           in graph
        param down_ref: ConanFileReference of who is depending on current node for this expansion
        """
        # basic node configuration
        conanref, conanfile = node

        new_reqs, new_options = self._config_node(conanfile, conanref, down_reqs, down_ref,
                                                  down_options)

        # Expand each one of the current requirements
        for name, require in conanfile.requires.iteritems():
            if require.override or require.conan_reference is None:
                continue
            previous_node = public_deps.get(name)
            if require.private or not previous_node:  # new node, must be added and expanded
                new_node = self._create_new_node(node, dep_graph, require, public_deps, name)
                if new_node:
                    # RECURSION!
                    self._load_deps(new_node, new_reqs, dep_graph, public_deps, conanref,
                                    new_options.copy())
            else:  # a public node already exist with this name
                if previous_node.conan_ref != require.conan_reference:
                    self._output.error("Conflict in %s\n"
                                       "    Requirement %s conflicts with already defined %s\n"
                                       "    Keeping %s\n"
                                       "    To change it, override it in your base requirements"
                                       % (conanref, require.conan_reference,
                                          previous_node.conan_ref, previous_node.conan_ref))
                dep_graph.add_edge(node, previous_node)
                # RECURSION!
                self._load_deps(previous_node, new_reqs, dep_graph, public_deps, conanref,
                                new_options.copy())

    def _config_node(self, conanfile, conanref, down_reqs, down_ref, down_options):
        """ update settings and option in the current ConanFile, computing actual
        requirement values, cause they can be overriden by downstream requires
        param settings: dict of settings values => {"os": "windows"}
        """
        try:
            conanfile.config()
            conanfile.options.propagate_upstream(down_options, down_ref, conanref, self._output)
            conanfile.config()

            new_options = conanfile.options.values

            conanfile.settings.validate()  # All has to be ok!
            conanfile.options.validate()

            # Update requirements (overwrites), computing new upstream
            conanfile.requires.output = self._output
            conanfile.requirements()
            new_down_reqs = conanfile.requires.update(down_reqs, self._output, conanref, down_ref)
        except ConanException as e:
            raise ConanException("%s: %s" % (conanref or "Conanfile", str(e)))
        return new_down_reqs, new_options

    def _create_new_node(self, current_node, dep_graph, requirement, public_deps, name_req):
        """ creates and adds a new node to the dependency graph
        """
        conanfile_path = self._retriever.get_conanfile(requirement.conan_reference)
        output = ScopedOutput(str(requirement.conan_reference), self._output)
        dep_conanfile = self._loader.load_conan(conanfile_path, output)
        if dep_conanfile:
            new_node = Node(requirement.conan_reference, dep_conanfile)
            dep_graph.add_node(new_node)
            dep_graph.add_edge(current_node, new_node)
            if not requirement.private:
                public_deps[name_req] = new_node
            # RECURSION!
            return new_node
        else:
            self._output.error("Could not retrieve %s" % requirement.conan_reference)
