import time

from conans.client.conanfile.configure import run_configure_method
from conans.client.graph.graph import DepsGraph, Node, RECIPE_EDITABLE, CONTEXT_HOST, CONTEXT_BUILD
from conans.errors import (ConanException, ConanExceptionInUserConanfileMethod,
                           conanfile_exception_formatter)
from conans.model.conan_file import get_env_context_manager
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirements, Requirement
from conans.util.log import logger


class DepsGraphBuilder(object):
    """
    This is a summary, in pseudo-code of the execution and structure of the graph
    resolution algorithm

    load_graph(root_node)
        init root_node
        expand_node(root_node)
            # 1. Evaluate requirements(), overrides, and version ranges
            get_node_requirements(node)
                node.conanfile.requirements()                         # call the requirements()
                resolve_cached_alias(node.conanfile.requires)         # replace cached alias
                update_requires_from_downstream(down_requires)        # process overrides
                resolve_ranges(node)                                  # resolve version-ranges
                    resolve_cached_alias(node.conanfile.requires)     # replace cached alias again

            # 2. Process each requires of this node
            for req in node.conanfile.requires:
                expand_require(req)
                    if req.name not in graph:                         # New node
                        new_node = create_new_node(req)               # fetch and load conanfile.py
                            if alias => create_new_node(alias)        # recurse alias
                        expand_node(new_node)                         # recursion
                    else:                                             # Node exists, closing diamond
                        resolve_cached_alias(req)
                        check_conflicts(req)                          # diamonds can cause conflicts
                        if need_recurse:                              # check for conflicts upstream
                            expand_node(previous_node)                # recursion
    """

    def __init__(self, proxy, output, loader, resolver, recorder):
        self._proxy = proxy
        self._output = output
        self._loader = loader
        self._resolver = resolver
        self._recorder = recorder

    def load_graph(self, root_node, check_updates, update, remotes, profile_host, profile_build,
                   graph_lock=None):
        check_updates = check_updates or update
        initial = graph_lock.initial_counter if graph_lock else None
        dep_graph = DepsGraph(initial_node_id=initial)
        # compute the conanfile entry point for this dependency graph
        root_node.public_closure.add(root_node)
        root_node.public_deps.add(root_node)
        root_node.transitive_closure[root_node.name] = root_node
        if profile_build:
            root_node.conanfile.settings_build = profile_build.processed_settings.copy()
            root_node.conanfile.settings_target = None
        dep_graph.add_node(root_node)

        # enter recursive computation
        t1 = time.time()
        self._expand_node(root_node, dep_graph, Requirements(), None, None, check_updates,
                          update, remotes, profile_host, profile_build, graph_lock)
        logger.debug("GRAPH: Time to load deps %s" % (time.time() - t1))
        return dep_graph

    def extend_build_requires(self, graph, node, build_requires_refs, check_updates, update,
                              remotes, profile_host, profile_build, graph_lock):
        # The options that will be defined in the node will be the real options values that have
        # been already propagated downstream from the dependency graph. This will override any
        # other possible option in the build_requires dependency graph. This means that in theory
        # an option conflict while expanding the build_requires is impossible
        node.conanfile.build_requires_options.clear_unscoped_options()
        new_options = node.conanfile.build_requires_options._reqs_options
        new_reqs = Requirements()

        conanfile = node.conanfile
        scope = conanfile.display_name

        build_requires = []
        for ref, context in build_requires_refs:
            r = Requirement(ref)
            r.build_require = True
            r.build_require_context = context
            build_requires.append(r)

        if graph_lock:
            graph_lock.pre_lock_node(node)
            # TODO: Add info about context?
            graph_lock.lock_node(node, build_requires, build_requires=True)

        self._resolve_ranges(graph, build_requires, scope, update, remotes)

        for br in build_requires:
            context_switch = bool(br.build_require_context == CONTEXT_BUILD)
            populate_settings_target = context_switch  # Avoid 'settings_target' for BR-host
            self._expand_require(br, node, graph, check_updates, update,
                                 remotes, profile_host, profile_build, new_reqs, new_options,
                                 graph_lock, context_switch=context_switch,
                                 populate_settings_target=populate_settings_target)

        new_nodes = set(n for n in graph.nodes if n.package_id is None)
        # This is to make sure that build_requires have precedence over the normal requires
        node.public_closure.sort(key_fn=lambda x: x not in new_nodes)
        return new_nodes

    def _expand_node(self, node, graph, down_reqs, down_ref, down_options, check_updates, update,
                     remotes, profile_host, profile_build, graph_lock):
        """ expands the dependencies of the node, recursively

        param node: Node object to be expanded in this step
        down_reqs: the Requirements as coming from downstream, which can overwrite current
                    values
        param down_ref: ConanFileReference of who is depending on current node for this expansion
        """
        # basic node configuration: calling configure() and requirements() and version-ranges
        new_options, new_reqs = self._get_node_requirements(node, graph, down_ref, down_options,
                                                            down_reqs, graph_lock, update, remotes)

        # Expand each one of the current requirements
        for require in node.conanfile.requires.values():
            if require.override:
                continue
            self._expand_require(require, node, graph, check_updates, update, remotes, profile_host,
                                 profile_build, new_reqs, new_options, graph_lock,
                                 context_switch=False)

    def _resolve_ranges(self, graph, requires, consumer, update, remotes):
        for require in requires:
            if require.locked_id:  # if it is locked, nothing to resolved
                continue
            self._resolver.resolve(require, consumer, update, remotes)
        self._resolve_cached_alias(requires, graph)

    @staticmethod
    def _resolve_cached_alias(requires, graph):
        if graph.aliased:
            for require in requires:
                alias = graph.aliased.get(require.ref)
                if alias:
                    require.ref = alias

    def _get_node_requirements(self, node, graph, down_ref, down_options, down_reqs, graph_lock,
                               update, remotes):
        """ compute the requirements of a node, evaluating requirements(), propagating
         the downstream requirements and overrides and solving version-ranges
        """
        # basic node configuration: calling configure() and requirements()
        if graph_lock:
            graph_lock.pre_lock_node(node)
        new_options = self._config_node(node, down_ref, down_options)
        # Alias that are cached should be replaced here, bc next requires.update() will warn if not
        self._resolve_cached_alias(node.conanfile.requires.values(), graph)

        if graph_lock:  # No need to evaluate, they are hardcoded in lockfile
            graph_lock.lock_node(node, node.conanfile.requires.values())

        # propagation of requirements can be necessary if some nodes are not locked
        new_reqs = node.conanfile.requires.update(down_reqs, self._output, node.ref, down_ref)
        # if there are version-ranges, resolve them before expanding each of the requirements
        # Resolve possible version ranges of the current node requirements
        # new_reqs is a shallow copy of what is propagated upstream, so changes done by the
        # RangeResolver are also done in new_reqs, and then propagated!
        conanfile = node.conanfile
        scope = conanfile.display_name
        self._resolve_ranges(graph, conanfile.requires.values(), scope, update, remotes)

        if not hasattr(conanfile, "_conan_evaluated_requires"):
            conanfile._conan_evaluated_requires = conanfile.requires.copy()
        elif conanfile.requires != conanfile._conan_evaluated_requires:
            raise ConanException("%s: Incompatible requirements obtained in different "
                                 "evaluations of 'requirements'\n"
                                 "    Previous requirements: %s\n"
                                 "    New requirements: %s"
                                 % (scope, list(conanfile._conan_evaluated_requires.values()),
                                    list(conanfile.requires.values())))

        return new_options, new_reqs

    def _expand_require(self, require, node, graph, check_updates, update, remotes, profile_host,
                        profile_build, new_reqs, new_options, graph_lock, context_switch,
                        populate_settings_target=True):
        # Handle a requirement of a node. There are 2 possibilities
        #    node -(require)-> new_node (creates a new node in the graph)
        #    node -(require)-> previous (creates a diamond with a previously existing node)

        # If the required is found in the node ancestors a loop is being closed
        context = CONTEXT_BUILD if context_switch else node.context
        name = require.ref.name  # TODO: allow bootstrapping, use references instead of names
        if node.ancestors.get(name, context) or (name == node.name and context == node.context):
            raise ConanException("Loop detected in context %s: '%s' requires '%s'"
                                 " which is an ancestor too" % (context, node.ref, require.ref))

        # If the requirement is found in the node public dependencies, it is a diamond
        previous = node.public_deps.get(name, context=context)
        previous_closure = node.public_closure.get(name, context=context)
        # build_requires and private will create a new node if it is not in the current closure
        if not previous or ((require.build_require or require.private) and not previous_closure):
            # new node, must be added and expanded (node -> new_node)
            new_node = self._create_new_node(node, graph, require, check_updates, update,
                                             remotes, profile_host, profile_build, graph_lock,
                                             context_switch=context_switch,
                                             populate_settings_target=populate_settings_target)

            # The closure of a new node starts with just itself
            new_node.public_closure.add(new_node)
            new_node.transitive_closure[new_node.name] = new_node
            # The new created node is connected to the parent one
            node.connect_closure(new_node)

            if require.private or require.build_require:
                # If the requirement is private (or build_require), a new public_deps is defined
                # the new_node doesn't propagate downstream the "node" consumer, so its public_deps
                # will be a copy of the node.public_closure, i.e. it can only cause conflicts in the
                # new_node.public_closure.
                new_node.public_deps.assign(node.public_closure)
                new_node.public_deps.add(new_node)
            else:
                node.transitive_closure[new_node.name] = new_node
                # Normal requires propagate and can conflict with the parent "node.public_deps" too
                new_node.public_deps.assign(node.public_deps)
                new_node.public_deps.add(new_node)

                # All the dependents of "node" are also connected now to "new_node"
                for dep_node in node.inverse_closure:
                    dep_node.connect_closure(new_node)

            # RECURSION, keep expanding (depth-first) the new node
            self._expand_node(new_node, graph, new_reqs, node.ref, new_options, check_updates,
                              update, remotes, profile_host, profile_build, graph_lock)
            if not require.private and not require.build_require:
                for name, n in new_node.transitive_closure.items():
                    node.transitive_closure[name] = n

        else:  # a public node already exist with this name
            self._resolve_cached_alias([require], graph)
            # As we are closing a diamond, there can be conflicts. This will raise if conflicts
            conflict = self._conflicting_references(previous, require.ref, node.ref)
            if conflict:  # It is possible to get conflict from alias, try to resolve it
                self._resolve_recipe(node, graph, require, check_updates,
                                     update, remotes, profile_host, graph_lock)
                # Maybe it was an ALIAS, so we can check conflict again
                conflict = self._conflicting_references(previous, require.ref, node.ref)
                if conflict:
                    raise ConanException(conflict)

            # Add current ancestors to the previous node and upstream deps
            for n in previous.public_closure:
                n.ancestors.add(node)
                for item in node.ancestors:
                    n.ancestors.add(item)

            node.connect_closure(previous)
            graph.add_edge(node, previous, require)
            if not require.private and not require.build_require:
                for name, n in previous.transitive_closure.items():
                    node.transitive_closure[name] = n

                # All the upstream dependencies (public_closure) of the previously existing node
                # now will be also connected to the node and to all its dependants
                for n in previous.transitive_closure.values():
                    node.connect_closure(n)
                    for dep_node in node.inverse_closure:
                        dep_node.connect_closure(n)

            # Recursion is only necessary if the inputs conflict with the current "previous"
            # configuration of upstream versions and options
            # recursion can stop if there is a graph_lock not relaxed
            lock_recurse = not (graph_lock and not graph_lock.relaxed)
            if lock_recurse and self._recurse(previous.public_closure, new_reqs, new_options,
                                              previous.context):
                self._expand_node(previous, graph, new_reqs, node.ref, new_options, check_updates,
                                  update, remotes, profile_host, profile_build, graph_lock)

    @staticmethod
    def _conflicting_references(previous, new_ref, consumer_ref=None):
        if previous.ref.copy_clear_rev() != new_ref.copy_clear_rev():
            if consumer_ref:
                return ("Conflict in %s:\n"
                        "    '%s' requires '%s' while '%s' requires '%s'.\n"
                        "    To fix this conflict you need to override the package '%s' "
                        "in your root package."
                        % (consumer_ref, consumer_ref, new_ref, next(iter(previous.dependants)).src,
                           previous.ref, new_ref.name))
            return True
        # Computed node, if is Editable, has revision=None
        # If new_ref.revision is None we cannot assume any conflict, the user hasn't specified
        # a revision, so it's ok any previous_ref
        if previous.ref.revision and new_ref.revision and previous.ref.revision != new_ref.revision:
            if consumer_ref:
                raise ConanException("Conflict in %s\n"
                                     "    Different revisions of %s has been requested"
                                     % (consumer_ref, new_ref))
            return True
        return False

    def _recurse(self, closure, new_reqs, new_options, context):
        """ For a given closure, if some requirements or options coming from downstream
        is incompatible with the current closure, then it is necessary to recurse
        then, incompatibilities will be raised as usually"""
        for req in new_reqs.values():
            n = closure.get(req.ref.name, context=context)
            if n and self._conflicting_references(n, req.ref):
                return True
        for pkg_name, options_values in new_options.items():
            n = closure.get(pkg_name, context=context)
            if n:
                options = n.conanfile.options
                for option, value in options_values.items():
                    if getattr(options, option) != value:
                        return True
        return False

    @staticmethod
    def _config_node(node, down_ref, down_options):
        """ update settings and option in the current ConanFile, computing actual
        requirement values, cause they can be overridden by downstream requires
        param settings: dict of settings values => {"os": "windows"}
        """
        conanfile, ref = node.conanfile, node.ref
        try:
            run_configure_method(conanfile, down_options, down_ref, ref)

            with get_env_context_manager(conanfile, without_python=True):
                # Update requirements (overwrites), computing new upstream
                if hasattr(conanfile, "requirements"):
                    # If re-evaluating the recipe, in a diamond graph, with different options,
                    # it could happen that one execution path of requirements() defines a package
                    # and another one a different package raising Duplicate dependency error
                    # Or the two consecutive calls, adding 2 different dependencies for the 2 paths
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
        except ConanExceptionInUserConanfileMethod:
            raise
        except ConanException as e:
            raise ConanException("%s: %s" % (ref or "Conanfile", str(e)))
        except Exception as e:
            raise ConanException(e)

        return new_options

    def _resolve_recipe(self, current_node, dep_graph, requirement, check_updates,
                        update, remotes, profile, graph_lock, original_ref=None):
        try:
            result = self._proxy.get_recipe(requirement.ref, check_updates, update,
                                            remotes, self._recorder)
        except ConanException as e:
            if current_node.ref:
                self._output.error("Failed requirement '%s' from '%s'"
                                   % (requirement.ref, current_node.conanfile.display_name))
            raise e
        conanfile_path, recipe_status, remote, new_ref = result

        locked_id = requirement.locked_id
        lock_py_requires = graph_lock.python_requires(locked_id) if locked_id is not None else None
        dep_conanfile = self._loader.load_conanfile(conanfile_path, profile, ref=requirement.ref,
                                                    lock_python_requires=lock_py_requires)
        if recipe_status == RECIPE_EDITABLE:
            dep_conanfile.in_local_cache = False
            dep_conanfile.develop = True

        if getattr(dep_conanfile, "alias", None):
            new_ref_norev = new_ref.copy_clear_rev()
            pointed_ref = ConanFileReference.loads(dep_conanfile.alias)
            dep_graph.aliased[new_ref_norev] = pointed_ref  # Caching the alias
            requirement.ref = pointed_ref
            if original_ref:  # So transitive alias resolve to the latest in the chain
                dep_graph.aliased[original_ref] = pointed_ref
            return self._resolve_recipe(current_node, dep_graph, requirement, check_updates,
                                        update, remotes, profile, graph_lock, original_ref)

        return new_ref, dep_conanfile, recipe_status, remote, locked_id

    def _create_new_node(self, current_node, dep_graph, requirement, check_updates,
                         update, remotes, profile_host, profile_build, graph_lock, context_switch,
                         populate_settings_target):
        # If there is a context_switch, it is because it is a BR-build
        if context_switch:
            profile = profile_build
            context = CONTEXT_BUILD
        else:
            profile = profile_host if current_node.context == CONTEXT_HOST else profile_build
            context = current_node.context

        result = self._resolve_recipe(current_node, dep_graph, requirement, check_updates, update,
                                      remotes, profile, graph_lock)
        new_ref, dep_conanfile, recipe_status, remote, locked_id = result

        # Assign the profiles depending on the context
        if profile_build:  # Keep existing behavior (and conanfile members) if no profile_build
            dep_conanfile.settings_build = profile_build.processed_settings.copy()
            if not context_switch:
                if populate_settings_target:
                    dep_conanfile.settings_target = current_node.conanfile.settings_target
                else:
                    dep_conanfile.settings_target = None
            else:
                if current_node.context == CONTEXT_HOST:
                    dep_conanfile.settings_target = profile_host.processed_settings.copy()
                else:
                    dep_conanfile.settings_target = profile_build.processed_settings.copy()

        logger.debug("GRAPH: new_node: %s" % str(new_ref))
        new_node = Node(new_ref, dep_conanfile, context=context)
        new_node.revision_pinned = requirement.ref.revision is not None
        new_node.recipe = recipe_status
        new_node.remote = remote
        # Ancestors are a copy of the parent, plus the parent itself
        new_node.ancestors.assign(current_node.ancestors)
        new_node.ancestors.add(current_node)

        if locked_id is not None:
            new_node.id = locked_id

        dep_graph.add_node(new_node)
        dep_graph.add_edge(current_node, new_node, requirement)
        return new_node
