import time
from collections import OrderedDict

from conans.client.graph.graph import DepsGraph, Node, RECIPE_EDITABLE
from conans.errors import (ConanException, ConanExceptionInUserConanfileMethod,
                           conanfile_exception_formatter)
from conans.model.conan_file import get_env_context_manager
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirements, Requirement
from conans.util.log import logger


REFERENCE_CONFLICT, REVISION_CONFLICT = 1, 2


class DepsGraphBuilder(object):
    """ Responsible for computing the dependencies graph DepsGraph
    """
    def __init__(self, proxy, output, loader, resolver, recorder):
        self._proxy = proxy
        self._output = output
        self._loader = loader
        self._resolver = resolver
        self._recorder = recorder

    def load_graph(self, root_node, check_updates, update, remote_name, processed_profile):
        check_updates = check_updates or update
        dep_graph = DepsGraph()
        # compute the conanfile entry point for this dependency graph
        name = root_node.name
        root_node.public_closure = OrderedDict([(name, root_node)])
        root_node.public_deps = {name: root_node}
        root_node.ancestors = set()
        dep_graph.add_node(root_node)

        # enter recursive computation
        t1 = time.time()
        self._load_deps(dep_graph, root_node, Requirements(), None, None,
                        check_updates, update, remote_name,
                        processed_profile)
        logger.debug("GRAPH: Time to load deps %s" % (time.time() - t1))
        return dep_graph

    def extend_build_requires(self, graph, node, build_requires_refs, check_updates, update,
                              remote_name, processed_profile):

        # The options that will be defined in the node will be the real options values that have
        # been already propagated downstream from the dependency graph. This will override any
        # other possible option in the build_requires dependency graph. This means that in theory
        # an option conflict while expanding the build_requires is impossible
        node.conanfile.build_requires_options.clear_unscoped_options()
        new_options = node.conanfile.build_requires_options._reqs_options
        new_reqs = Requirements()

        conanfile = node.conanfile
        scope = conanfile.display_name
        requires = [Requirement(ref) for ref in build_requires_refs]
        self._resolve_ranges(graph, requires, scope, update, remote_name)

        for require in requires:
            name = require.ref.name
            require.build_require = True
            self._handle_require(name, node, require, graph, check_updates, update,
                                 remote_name, processed_profile, new_reqs, new_options)

        new_nodes = set([n for n in graph.nodes if n.package_id is None])
        # This is to make sure that build_requires have precedence over the normal requires
        ordered_closure = list(node.public_closure.items())
        ordered_closure.sort(key=lambda x: x[1] not in new_nodes)
        node.public_closure = OrderedDict(ordered_closure)

        subgraph = DepsGraph()
        subgraph.aliased = graph.aliased
        subgraph.evaluated = graph.evaluated
        subgraph.nodes = new_nodes
        for n in subgraph.nodes:
            n.build_require = True

        return subgraph

    def _resolve_ranges(self, graph, requires, scope, update, remote_name):
        for require in requires:
            self._resolver.resolve(require, scope, update, remote_name)

        # After resolving ranges,
        for require in requires:
            alias = graph.aliased.get(require.ref)
            if alias:
                require.ref = alias

    def _resolve_deps(self, graph, node, update, remote_name):
        # Resolve possible version ranges of the current node requirements
        # new_reqs is a shallow copy of what is propagated upstream, so changes done by the
        # RangeResolver are also done in new_reqs, and then propagated!
        conanfile = node.conanfile
        scope = conanfile.display_name
        self._resolve_ranges(graph, conanfile.requires.values(), scope, update, remote_name)

        if not hasattr(conanfile, "_conan_evaluated_requires"):
            conanfile._conan_evaluated_requires = conanfile.requires.copy()
        elif conanfile.requires != conanfile._conan_evaluated_requires:
            raise ConanException("%s: Incompatible requirements obtained in different "
                                 "evaluations of 'requirements'\n"
                                 "    Previous requirements: %s\n"
                                 "    New requirements: %s"
                                 % (scope, list(conanfile._conan_evaluated_requires.values()),
                                    list(conanfile.requires.values())))

    def _load_deps(self, dep_graph, node, down_reqs, down_ref, down_options,
                   check_updates, update, remote_name, processed_profile):
        """ expands the dependencies of the node, recursively
        param node: Node object to be expanded in this step
        down_reqs: the Requirements as coming from downstream, which can overwrite current
                    values
        param down_ref: ConanFileReference of who is depending on current node for this expansion
        """
        # basic node configuration: calling configure() and requirements()
        new_reqs, new_options = self._config_node(dep_graph, node, down_reqs, down_ref, down_options)
        # if there are version-ranges, resolve them before expanding each of the requirements
        self._resolve_deps(dep_graph, node, update, remote_name)

        # Expand each one of the current requirements
        for name, require in node.conanfile.requires.items():
            if require.override:
                continue

            self._handle_require(name, node, require, dep_graph, check_updates, update,
                                 remote_name, processed_profile, new_reqs, new_options)

    def _handle_require(self, name, node, require, dep_graph, check_updates, update,
                        remote_name, processed_profile, new_reqs, new_options):
        if name in node.ancestors or name == node.name:
            raise ConanException("Loop detected: '%s' requires '%s' which is an ancestor too"
                                 % (node.ref, require.ref))

        previous = node.public_deps.get(name)
        previous_closure = node.public_closure.get(name)
        if not previous or ((require.build_require or require.private) and not previous_closure):
            # new node, must be added and expanded
            # node -> new_node
            new_node = self._create_new_node(node, dep_graph, require, name,
                                             check_updates, update, remote_name,
                                             processed_profile)

            # The closure of a new node starts with just itself
            new_node.public_closure = OrderedDict([(new_node.ref.name, new_node)])
            node.public_closure[name] = new_node
            new_node.inverse_closure.add(node)
            node.public_deps[new_node.name] = new_node

            # New nodes will inherit the private property of its ancestor
            new_node.private = node.private or require.private
            if require.private or require.build_require:
                # If the requirement is private (or build_require), a new public scope is defined
                new_node.public_deps = node.public_closure.copy()
                new_node.public_deps[name] = new_node
            else:
                new_node.public_deps = node.public_deps.copy()
                new_node.public_deps[name] = new_node

                # Update the closure of each dependent
                for dep_node in node.inverse_closure:
                    dep_node.public_closure[new_node.name] = new_node
                    new_node.inverse_closure.add(dep_node)
                    dep_node.public_deps[new_node.name] = new_node

            # RECURSION!
            self._load_deps(dep_graph, new_node, new_reqs, node.ref,
                            new_options, check_updates, update,
                            remote_name, processed_profile)
        else:  # a public node already exist with this name
            # This is closing a diamond, the node is existing in the scope
            alias_ref = dep_graph.aliased.get(require.ref)
            # Necessary to make sure that it is pointing to the correct aliased
            if alias_ref:
                require.ref = alias_ref
            conflict = self._conflicting_references(previous.ref, require.ref)
            if conflict == REVISION_CONFLICT:  # Revisions conflict
                raise ConanException("Conflict in %s\n"
                                     "    Different revisions of %s has been requested"
                                     % (node.ref, require.ref))
            elif conflict == REFERENCE_CONFLICT:
                raise ConanException("Conflict in %s\n"
                                     "    Requirement %s conflicts with already defined %s\n"
                                     "    To change it, override it in your base requirements"
                                     % (node.ref, require.ref, previous.ref))

            # Add current ancestors to the previous node
            previous.update_ancestors(node.ancestors.union([node.name]))
            if previous.private and not require.private:
                previous.make_public()

            node.public_closure[name] = previous
            previous.inverse_closure.add(node)
            node.public_deps[name] = previous
            dep_graph.add_edge(node, previous, require.private, require.build_require)
            # Update the closure of each dependent
            for name, n in previous.public_closure.items():
                if n.build_require or n.private:
                    continue
                node.public_closure[name] = n
                n.inverse_closure.add(node)
                for dep_node in node.inverse_closure:
                    dep_node.public_closure[name] = n
                    dep_node.public_deps[name] = n
                    n.inverse_closure.add(dep_node)

            # RECURSION!
            if self._recurse(previous.public_closure, new_reqs, new_options):
                self._load_deps(dep_graph, previous, new_reqs, node.ref,
                                new_options, check_updates, update,
                                remote_name, processed_profile)

    @staticmethod
    def _conflicting_references(previous_ref, new_ref):
        if previous_ref.copy_clear_rev() != new_ref.copy_clear_rev():
            return REFERENCE_CONFLICT
        # Computed node, if is Editable, has revision=None
        # If new_ref.revision is None we cannot assume any conflict, the user hasn't specified
        # a revision, so it's ok any previous_ref
        if previous_ref.revision and new_ref.revision and previous_ref.revision != new_ref.revision:
            return REVISION_CONFLICT
        return False

    def _recurse(self, closure, new_reqs, new_options):
        """ For a given closure, if some requirements or options coming from downstream
        is incompatible with the current closure, then it is necessary to recurse
        then, incompatibilities will be raised as usually"""
        for req in new_reqs.values():
            n = closure.get(req.ref.name)
            if n and self._conflicting_references(n.ref, req.ref):
                return True
        for pkg_name, options_values in new_options.items():
            n = closure.get(pkg_name)
            if n:
                options = n.conanfile.options
                for option, value in options_values.items():
                    if getattr(options, option) != value:
                        return True
        return False

    def _config_node(self, graph, node, down_reqs, down_ref, down_options):
        """ update settings and option in the current ConanFile, computing actual
        requirement values, cause they can be overridden by downstream requires
        param settings: dict of settings values => {"os": "windows"}
        """
        try:
            conanfile, ref = node.conanfile, node.ref
            # Avoid extra time manipulating the sys.path for python
            with get_env_context_manager(conanfile, without_python=True):
                if hasattr(conanfile, "config"):
                    if not ref:
                        conanfile.output.warn("config() has been deprecated."
                                              " Use config_options and configure")
                    with conanfile_exception_formatter(str(conanfile), "config"):
                        conanfile.config()
                with conanfile_exception_formatter(str(conanfile), "config_options"):
                    conanfile.config_options()
                conanfile.options.propagate_upstream(down_options, down_ref, ref)
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
                if graph.aliased:
                    for req in conanfile.requires.values():
                        req.ref = graph.aliased.get(req.ref, req.ref)
                new_down_reqs = conanfile.requires.update(down_reqs, self._output, ref, down_ref)
        except ConanExceptionInUserConanfileMethod:
            raise
        except ConanException as e:
            raise ConanException("%s: %s" % (ref or "Conanfile", str(e)))
        except Exception as e:
            raise ConanException(e)

        return new_down_reqs, new_options

    def _create_new_node(self, current_node, dep_graph, requirement, name_req,
                         check_updates, update, remote_name, processed_profile, alias_ref=None):
        """ creates and adds a new node to the dependency graph
        """

        try:
            result = self._proxy.get_recipe(requirement.ref, check_updates, update,
                                            remote_name, self._recorder)
        except ConanException as e:
            if current_node.ref:
                self._output.error("Failed requirement '%s' from '%s'"
                                   % (requirement.ref,
                                      current_node.conanfile.display_name))
            raise e
        conanfile_path, recipe_status, remote, new_ref = result

        dep_conanfile = self._loader.load_conanfile(conanfile_path, processed_profile,
                                                    ref=requirement.ref)
        if recipe_status == RECIPE_EDITABLE:
            dep_conanfile.in_local_cache = False
            dep_conanfile.develop = True

        if getattr(dep_conanfile, "alias", None):
            alias_ref = alias_ref or new_ref.copy_clear_rev()
            requirement.ref = ConanFileReference.loads(dep_conanfile.alias)
            dep_graph.aliased[alias_ref] = requirement.ref
            return self._create_new_node(current_node, dep_graph, requirement,
                                         name_req, check_updates, update,
                                         remote_name, processed_profile,
                                         alias_ref=alias_ref)

        logger.debug("GRAPH: new_node: %s" % str(new_ref))
        new_node = Node(new_ref, dep_conanfile)
        new_node.revision_pinned = requirement.ref.revision is not None
        new_node.recipe = recipe_status
        new_node.remote = remote
        new_node.ancestors = current_node.ancestors.copy()
        new_node.ancestors.add(current_node.name)
        dep_graph.add_node(new_node)
        dep_graph.add_edge(current_node, new_node, requirement.private, requirement.build_require)
        return new_node
