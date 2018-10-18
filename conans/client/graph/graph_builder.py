import time

from conans.model.conan_file import get_env_context_manager
from conans.model.requires import Requirements
from conans.model.ref import ConanFileReference
from conans.errors import (ConanException, conanfile_exception_formatter,
                           ConanExceptionInUserConanfileMethod)
from conans.client.output import ScopedOutput
from conans.util.log import logger
from conans.client.graph.graph import DepsGraph, Node, RECIPE_WORKSPACE
from conans.model.workspace import WORKSPACE_FILE
from collections import namedtuple
import json
from conans.model.options import OptionsValues
from collections import defaultdict


GraphLockDependency = namedtuple("GraphLockDependency", "node_id private")


class GraphLock(object):

    def __init__(self, graph):
        self._nodes = {}  # id: conan_ref, binaryID, options_values, dependencies
        for node in graph.nodes:
            if node.conan_ref is None:
                continue
            id_ = str(id(node))
            conan_ref = node.conan_ref
            binary_id = node.conanfile.info.package_id()
            options_values = node.conanfile.options.values
            dependencies = []
            for edge in node.dependencies:
                dependencies.append(GraphLockDependency(str(id(edge.dst)), edge.private))

            self._nodes[id_] = conan_ref, binary_id, options_values, dependencies

    def build_order(self, node_id):
        inverse_neighbors = defaultdict(set)
        for id_, node in self._nodes.items():
            for d in node[3]:
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
        return result

    def conan_ref(self, node_id):
        return self._nodes[node_id][0]

    def options_values(self, node_id):
        return self._nodes[node_id][2]

    def dependencies(self, node_id):
        return self._nodes[node_id][3]

    @staticmethod
    def loads(text):
        graph_lock = GraphLock(DepsGraph())
        graph_json = json.loads(text)
        for id_, graph_node in graph_json.items():
            try:
                conan_ref = ConanFileReference.loads(graph_node["conan_ref"])
            except ConanException:
                conan_ref = None
            binary_id = graph_node["binary_id"]
            options_values = OptionsValues.loads(graph_node["options"])
            dependencies = [GraphLockDependency(n[0], n[1])
                            for n in graph_node["dependencies"]]
            node = conan_ref, binary_id, options_values, dependencies
            graph_lock._nodes[id_] = node
        return graph_lock

    def dumps(self):
        result = {}
        for id_, node in self._nodes.items():
            result[id_] = {"conan_ref": str(node[0]),
                           "binary_id": node[1],
                           "options": node[2].dumps(),
                           "dependencies": node[3]}
        return json.dumps(result, indent=True)


class DepsGraphLockBuilder(object):
    def __init__(self, proxy, output, loader, recorder):
        self._proxy = proxy
        self._output = output
        self._loader = loader
        self._recorder = recorder

    def load_graph(self, remote_name, processed_profile, node_id, graph_lock):
        """graph_lock: #NodeId: Pkg/version@user/channel#RR:#ID#BR
        """
        dep_graph = DepsGraph()
        # compute the conanfile entry point for this dependency graph
        current_node_id = node_id  # FIXME!!!
        reference = graph_lock.conan_ref(node_id)
        if reference is None:
            pass
        else:
            root_node = self._create_new_node_simple(reference, processed_profile,
                                                     remote_name)
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

        options_values = graph_lock.options_values(current_node_id)
        self._config_node(node, options_values)

        # Defining explicitly the requires
        requires = Requirements()
        for dependency in graph_lock.dependencies(current_node_id):
            dep_ref = graph_lock.conan_ref(dependency.node_id)
            requires.add(str(dep_ref), dependency.private)

            previous = visited_deps.get(dep_ref)
            if not previous:  # new node, must be added and expanded
                new_node = self._create_new_node(node, dep_graph, dep_ref,
                                                 dependency.private,
                                                 remote_name, processed_profile)
                # RECURSION!
                self._load_deps(new_node, dep_graph, visited_deps, remote_name, processed_profile,
                                graph_lock, dependency.node_id)
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
        new_node = self._create_new_node_simple(reference, processed_profile, remote_name)
        dep_graph.add_node(new_node)
        dep_graph.add_edge(current_node, new_node, private)
        return new_node

    def _create_new_node_simple(self, reference, processed_profile, remote_name):
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
        return new_node


class DepsGraphBuilder(object):
    """ Responsible for computing the dependencies graph DepsGraph
    """
    def __init__(self, proxy, output, loader, resolver, workspace, recorder):
        self._proxy = proxy
        self._output = output
        self._loader = loader
        self._resolver = resolver
        self._workspace = workspace
        self._recorder = recorder

    def load_graph(self, conanfile, check_updates, update, remote_name, processed_profile):
        check_updates = check_updates or update
        dep_graph = DepsGraph()
        # compute the conanfile entry point for this dependency graph
        root_node = Node(None, conanfile)
        dep_graph.add_node(root_node)
        public_deps = {}  # {name: Node} dict with public nodes, so they are not added again
        aliased = {}
        # enter recursive computation
        t1 = time.time()
        loop_ancestors = []
        self._load_deps(root_node, Requirements(), dep_graph, public_deps, None, None,
                        loop_ancestors, aliased, check_updates, update, remote_name,
                        processed_profile)
        logger.debug("Deps-builder: Time to load deps %s" % (time.time() - t1))
        t1 = time.time()
        dep_graph.compute_package_ids()
        logger.debug("Deps-builder: Propagate info %s" % (time.time() - t1))
        return dep_graph

    def _resolve_deps(self, node, aliased, update, remote_name):
        # Resolve possible version ranges of the current node requirements
        # new_reqs is a shallow copy of what is propagated upstream, so changes done by the
        # RangeResolver are also done in new_reqs, and then propagated!
        conanfile, conanref = node.conanfile, node.conan_ref
        for _, require in conanfile.requires.items():
            self._resolver.resolve(require, conanref, update, remote_name)

        # After resolving ranges,
        for req in conanfile.requires.values():
            alias = aliased.get(req.conan_reference)
            if alias:
                req.conan_reference = alias

        if not hasattr(conanfile, "_conan_evaluated_requires"):
            conanfile._conan_evaluated_requires = conanfile.requires.copy()
        elif conanfile.requires != conanfile._conan_evaluated_requires:
            raise ConanException("%s: Incompatible requirements obtained in different "
                                 "evaluations of 'requirements'\n"
                                 "    Previous requirements: %s\n"
                                 "    New requirements: %s"
                                 % (conanref, list(conanfile._conan_evaluated_requires.values()),
                                    list(conanfile.requires.values())))

    def _load_deps(self, node, down_reqs, dep_graph, public_deps, down_ref, down_options,
                   loop_ancestors, aliased, check_updates, update, remote_name, processed_profile):
        """ loads a Conan object from the given file
        param node: Node object to be expanded in this step
        down_reqs: the Requirements as coming from downstream, which can overwrite current
                    values
        param deps: DepsGraph result
        param public_deps: {name: Node} of already expanded public Nodes, not to be repeated
                           in graph
        param down_ref: ConanFileReference of who is depending on current node for this expansion
        """
        # basic node configuration
        new_reqs, new_options = self._config_node(node, down_reqs, down_ref, down_options, aliased)

        self._resolve_deps(node, aliased, update, remote_name)

        # Expand each one of the current requirements
        for name, require in node.conanfile.requires.items():
            if require.override:
                continue
            if require.conan_reference in loop_ancestors:
                raise ConanException("Loop detected: %s"
                                     % "->".join(str(r) for r in loop_ancestors))
            new_loop_ancestors = loop_ancestors[:]  # Copy for propagating
            new_loop_ancestors.append(require.conan_reference)
            previous = public_deps.get(name)
            if require.private or not previous:  # new node, must be added and expanded
                new_node = self._create_new_node(node, dep_graph, require, public_deps, name,
                                                 aliased, check_updates, update, remote_name,
                                                 processed_profile)
                # RECURSION!
                # Make sure the subgraph is truly private
                new_public_deps = {} if require.private else public_deps
                self._load_deps(new_node, new_reqs, dep_graph, new_public_deps, node.conan_ref,
                                new_options, new_loop_ancestors, aliased, check_updates, update,
                                remote_name, processed_profile)
            else:  # a public node already exist with this name
                previous_node, closure = previous
                alias_ref = aliased.get(require.conan_reference, require.conan_reference)
                # Necessary to make sure that it is pointing to the correct aliased
                require.conan_reference = alias_ref
                if previous_node.conan_ref != alias_ref:
                    raise ConanException("Conflict in %s\n"
                                         "    Requirement %s conflicts with already defined %s\n"
                                         "    Keeping %s\n"
                                         "    To change it, override it in your base requirements"
                                         % (node.conan_ref, require.conan_reference,
                                            previous_node.conan_ref, previous_node.conan_ref))
                dep_graph.add_edge(node, previous_node)
                # RECURSION!
                if closure is None:
                    closure = dep_graph.closure(node)
                    public_deps[name] = previous_node, closure
                if self._recurse(closure, new_reqs, new_options):
                    self._load_deps(previous_node, new_reqs, dep_graph, public_deps, node.conan_ref,
                                    new_options, new_loop_ancestors, aliased, check_updates, update,
                                    remote_name, processed_profile)

    def _recurse(self, closure, new_reqs, new_options):
        """ For a given closure, if some requirements or options coming from downstream
        is incompatible with the current closure, then it is necessary to recurse
        then, incompatibilities will be raised as usually"""
        for req in new_reqs.values():
            n = closure.get(req.conan_reference.name)
            if n and n.conan_ref != req.conan_reference:
                return True
        for pkg_name, options_values in new_options.items():
            n = closure.get(pkg_name)
            if n:
                options = n.conanfile.options
                for option, value in options_values.items():
                    if getattr(options, option) != value:
                        return True
        return False

    def _config_node(self, node, down_reqs, down_ref, down_options, aliased):
        """ update settings and option in the current ConanFile, computing actual
        requirement values, cause they can be overridden by downstream requires
        param settings: dict of settings values => {"os": "windows"}
        """
        try:
            conanfile, conanref = node.conanfile, node.conan_ref
            # Avoid extra time manipulating the sys.path for python
            with get_env_context_manager(conanfile, without_python=True):
                if hasattr(conanfile, "config"):
                    if not conanref:
                        output = ScopedOutput(str("PROJECT"), self._output)
                        output.warn("config() has been deprecated."
                                    " Use config_options and configure")
                    with conanfile_exception_formatter(str(conanfile), "config"):
                        conanfile.config()
                with conanfile_exception_formatter(str(conanfile), "config_options"):
                    conanfile.config_options()
                conanfile.options.propagate_upstream(down_options, down_ref, conanref)
                if hasattr(conanfile, "config"):
                    with conanfile_exception_formatter(str(conanfile), "config"):
                        conanfile.config()

                with conanfile_exception_formatter(str(conanfile), "configure"):
                    conanfile.configure()

                conanfile.settings.validate()  # All has to be ok!
                conanfile.options.validate()

                # Update requirements (overwrites), computing new upstream
                if hasattr(conanfile, "requirements"):
                    # If re-evaluating the recipe, in a diamond graph, with different options,
                    # it could happen that one execution path of requirements() defines a package
                    # and another one a different package raising Duplicate dependency error
                    # Or the two consecutive calls, adding 2 different dependencies for the two paths
                    # So it is necessary to save the "requires" state and restore it before a second
                    # execution of requirements(). It is a shallow copy, if first iteration is
                    # RequireResolve'd or overridden, the inner requirements are modified
                    if not hasattr(conanfile, "_conan_original_requires"):
                        conanfile._conan_original_requires = conanfile.requires.copy()
                    else:
                        conanfile.requires = conanfile._conan_original_requires.copy()

                    with conanfile_exception_formatter(str(conanfile), "requirements"):
                        conanfile.requirements()

                new_options = conanfile.options.deps_package_values
                if aliased:
                    for req in conanfile.requires.values():
                        req.conan_reference = aliased.get(req.conan_reference,
                                                          req.conan_reference)
                new_down_reqs = conanfile.requires.update(down_reqs, self._output,
                                                          conanref, down_ref)
        except ConanExceptionInUserConanfileMethod:
            raise
        except ConanException as e:
            raise ConanException("%s: %s" % (conanref or "Conanfile", str(e)))
        except Exception as e:
            raise ConanException(e)

        return new_down_reqs, new_options

    def _create_new_node(self, current_node, dep_graph, requirement, public_deps, name_req, aliased,
                         check_updates, update, remote_name, processed_profile, alias_ref=None):
        """ creates and adds a new node to the dependency graph
        """
        workspace_package = self._workspace[requirement.conan_reference] if self._workspace else None
        if workspace_package:
            conanfile_path = workspace_package.conanfile_path
            recipe_status = RECIPE_WORKSPACE
            remote = WORKSPACE_FILE
        else:
            try:
                result = self._proxy.get_recipe(requirement.conan_reference,
                                                check_updates, update, remote_name, self._recorder)
            except ConanException as e:
                base_ref = str(current_node.conan_ref or "PROJECT")
                self._output.error("Failed requirement '%s' from '%s'"
                                   % (requirement.conan_reference, base_ref))
                raise e
            conanfile_path, recipe_status, remote, _ = result

        output = ScopedOutput(str(requirement.conan_reference), self._output)
        dep_conanfile = self._loader.load_conanfile(conanfile_path, output, processed_profile,
                                                    reference=requirement.conan_reference)

        if workspace_package:
            workspace_package.conanfile = dep_conanfile
        if getattr(dep_conanfile, "alias", None):
            alias_reference = alias_ref or requirement.conan_reference
            requirement.conan_reference = ConanFileReference.loads(dep_conanfile.alias)
            aliased[alias_reference] = requirement.conan_reference
            return self._create_new_node(current_node, dep_graph, requirement, public_deps,
                                         name_req, aliased, check_updates, update,
                                         remote_name, processed_profile, alias_ref=alias_reference)

        new_node = Node(requirement.conan_reference, dep_conanfile)
        new_node.recipe = recipe_status
        new_node.remote = remote
        dep_graph.add_node(new_node)
        dep_graph.add_edge(current_node, new_node, requirement.private)
        if not requirement.private:
            public_deps[name_req] = new_node, None
        return new_node
