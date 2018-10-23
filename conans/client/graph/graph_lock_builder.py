from collections import defaultdict
from collections import namedtuple
import json

from conans.client.graph.graph import DepsGraph, Node
from conans.client.output import ScopedOutput
from conans.client.profile_loader import _load_profile
from conans.errors import (ConanException, conanfile_exception_formatter,
                           ConanExceptionInUserConanfileMethod)
from conans.model.conan_file import get_env_context_manager
from conans.model.options import OptionsValues
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.requires import Requirements


GraphLockDependency = namedtuple("GraphLockDependency", "node_id private build_require")
GraphLockNode = namedtuple("GraphLockNode", "conan_ref binary_id options_values dependencies")


class GraphLock(object):

    def __init__(self, graph, profile):
        self._profile = profile
        self._nodes = {}  # id: conan_ref, binaryID, options_values, dependencies
        for node in graph.nodes:
            id_ = str(id(node))
            conan_ref = node.conan_ref
            binary_id = node.conanfile.info.package_id()
            options_values = node.conanfile.options.values
            dependencies = []
            for edge in node.dependencies:
                dependencies.append(GraphLockDependency(str(id(edge.dst)), edge.private,
                                                        edge.build_require))

            self._nodes[id_] = GraphLockNode(conan_ref, binary_id, options_values, dependencies)

    @property
    def profile(self):
        return self._profile

    def get_node_from_ref(self, conan_ref):
        for id_, node in self._nodes.items():
            if node.conan_ref == conan_ref:
                return id_

    def build_order(self, node_id):
        inverse_neighbors = defaultdict(set)
        for id_, node in self._nodes.items():
            for d in node.dependencies:
                inverse_neighbors[d.node_id].add(id_)
        # first compute dependents closure
        if node_id:
            closure = set()
            current = [node_id]
            closure.update(current)
            while current:
                new_current = set()
                for n in current:
                    closure.add(n)
                    new_neighs = inverse_neighbors[n]
                    to_add = set(new_neighs).difference(current)
                    new_current.update(to_add)
                current = new_current
        else:
            closure = set(self._nodes.keys())

        # Then, order by levels
        current_level = []
        levels = [current_level]
        opened = closure.copy()
        while opened:
            current = opened.copy()
            for o in opened:
                o_neighs = inverse_neighbors[o]
                if not any(n in opened for n in o_neighs):
                    current_level.append(o)
                    current.discard(o)
            current_level.sort()
            # now initialize new level
            opened = current
            if opened:
                current_level = []
                levels.append(current_level)

        # closure following levels
        result = []
        for level in reversed(levels):
            new_level = [n for n in level if (n in closure)]
            if new_level:
                result.append(new_level)

        references = []
        for level in result:
            level_refs = []
            for node_id in level:
                node = self._nodes[node_id]
                ref = node.conan_ref
                if ref is None:  # root consumer is not in build_order
                    continue
                id_ = node.binary_id
                pkg_ref = PackageReference(ref, id_)
                level_refs.append(pkg_ref)
            if level_refs:
                references.append(level_refs)

        return references

    def conan_ref(self, node_id):
        return self._nodes[node_id].conan_ref

    def options_values(self, node_id):
        return self._nodes[node_id].options_values

    def dependencies(self, node_id):
        return self._nodes[node_id].dependencies

    @staticmethod
    def loads(text):
        graph_json = json.loads(text)
        profile = graph_json["profile"]
        # FIXME: Reading private very ugly
        profile, _ = _load_profile(profile, None, None)
        graph_lock = GraphLock(DepsGraph(), profile)
        for id_, graph_node in graph_json["graph"].items():
            try:
                conan_ref = ConanFileReference.loads(graph_node["conan_ref"])
            except ConanException:
                conan_ref = None
            binary_id = graph_node["binary_id"]
            options_values = OptionsValues.loads(graph_node["options"])
            dependencies = [GraphLockDependency(n[0], n[1], n[2])
                            for n in graph_node["dependencies"]]
            node = GraphLockNode(conan_ref, binary_id, options_values, dependencies)
            graph_lock._nodes[id_] = node
        return graph_lock

    def dumps(self):
        result = {"profile": self._profile.dumps()}
        graph = {}
        for id_, node in self._nodes.items():
            graph[id_] = {"conan_ref": str(node.conan_ref),
                          "binary_id": node.binary_id,
                          "options": node.options_values.dumps(),
                          "dependencies": node.dependencies}
        result["graph"] = graph
        return json.dumps(result, indent=True)


class DepsGraphLockBuilder(object):
    def __init__(self, proxy, output, loader, recorder):
        self._proxy = proxy
        self._output = output
        self._loader = loader
        self._recorder = recorder

    def expand_build_requires(self, node, graph_lock):
        
    def load_graph(self, root_node, remote_name, processed_profile, graph_lock,
                   graph_lock_root_node):
        dep_graph = DepsGraph()
        current_node_id = graph_lock_root_node
        dep_graph.add_node(root_node)
        # enter recursive computation
        visited_deps = {}
        self._load_deps(root_node, dep_graph, visited_deps, remote_name, processed_profile,
                        graph_lock, current_node_id)
        dep_graph.compute_package_ids()
        # TODO: Implement BinaryID check against graph_lock
        return dep_graph

    def _load_deps(self, node, dep_graph, visited_deps, remote_name, processed_profile,
                   graph_lock, current_node_id):

        if current_node_id:
            options_values = graph_lock.options_values(current_node_id)
            self._config_node(node, options_values)
            dependencies = graph_lock.dependencies(current_node_id)
        else:
            # This is a virtual, we need to extract the required reference
            ref = node.conanfile.requires.values()[0].conan_reference
            node_ref = graph_lock.get_node_from_ref(ref)
            dependencies = [GraphLockDependency(node_ref, False, False)]
        # Defining explicitly the requires
        requires = Requirements()
        for dependency in dependencies:
            if dependency.build_require:
                continue
            dep_id = dependency.node_id
            dep_ref = graph_lock.conan_ref(dep_id)
            requires.add(str(dep_ref), dependency.private)

            previous = visited_deps.get(dep_ref)
            if not previous:  # new node, must be added and expanded
                new_node = self._create_new_node(node, dep_graph, dep_ref,
                                                 dependency.private,
                                                 remote_name, processed_profile)
                # RECURSION!
                self._load_deps(new_node, dep_graph, visited_deps, remote_name, processed_profile,
                                graph_lock, dep_id)
                visited_deps[dep_ref] = new_node
            else:
                dep_graph.add_edge(node, previous)

        # Just in case someone is checking it
        node.conanfile.requires = requires

    def _config_node(self, node, options_values):
        try:
            conanfile, conanref = node.conanfile, node.conan_ref
            # Avoid extra time manipulating the sys.path for python
            with get_env_context_manager(conanfile, without_python=True):
                with conanfile_exception_formatter(str(conanfile), "config_options"):
                    conanfile.config_options()
                conanfile.options.values = options_values
                with conanfile_exception_formatter(str(conanfile), "configure"):
                    conanfile.configure()

                conanfile.settings.validate()  # All has to be ok!
                conanfile.options.validate()
        except ConanExceptionInUserConanfileMethod:
            raise
        except ConanException as e:
            raise ConanException("%s: %s" % (conanref or "Conanfile", str(e)))
        except Exception as e:
            raise ConanException(e)

    def _create_new_node(self, current_node, dep_graph, reference, private,
                         remote_name, processed_profile):
        try:
            result = self._proxy.get_recipe(reference,
                                            False, False, remote_name, self._recorder)
        except ConanException as e:
            self._output.error("Failed requirement '%s'" % (reference,))
            raise e
        conanfile_path, recipe_status, remote, _ = result

        output = ScopedOutput(str(reference), self._output)
        dep_conanfile = self._loader.load_conanfile(conanfile_path, output, processed_profile,
                                                    reference=reference)

        new_node = Node(reference, dep_conanfile)
        new_node.recipe = recipe_status
        new_node.remote = remote
        dep_graph.add_node(new_node)
        dep_graph.add_edge(current_node, new_node, private)
        return new_node
