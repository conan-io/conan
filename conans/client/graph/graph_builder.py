import fnmatch

from conans.client.conanfile.configure import run_configure_method
from conans.client.graph.graph import DepsGraph, Node, RECIPE_EDITABLE, CONTEXT_HOST, CONTEXT_BUILD, \
    RECIPE_MISSING, RECIPE_CONSUMER, GraphError

from conans.errors import ConanException, conanfile_exception_formatter
from conans.model.ref import ConanFileReference
from conans.model.requires import BuildRequirements, TestRequirements


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

    class StopRecursion(Exception):
        pass

    def __init__(self, proxy, output, loader, resolver):
        self._proxy = proxy
        self._output = output
        self._loader = loader
        self._resolver = resolver

    def load_graph(self, root_node, check_updates, update, remotes, profile_host, profile_build,
                   graph_lock=None):
        assert profile_host is not None
        assert profile_build is not None
        print("Loading graph")
        check_updates = check_updates or update
        initial = graph_lock.initial_counter if graph_lock else None
        dep_graph = DepsGraph(initial_node_id=initial)

        # TODO: Why assign here the settings_build and settings_target?
        root_node.conanfile.settings_build = profile_build.processed_settings.copy()
        root_node.conanfile.settings_target = None
        self._prepare_node(root_node, profile_host, profile_build, graph_lock, None, None)
        dep_graph.add_node(root_node)

        # enter recursive computation
        try:
            self._expand_node(root_node, dep_graph, check_updates,
                              update, remotes, profile_host, profile_build, graph_lock)
        except DepsGraphBuilder.StopRecursion as e:
            dep_graph.error = str(e)
        else:
            self._check_provides(dep_graph)
        return dep_graph

    @staticmethod
    def _add_profile_build_requires(node, profile_host, profile_build):
        profile = profile_host if node.context == CONTEXT_HOST else profile_build
        build_requires = profile.build_requires
        str_ref = str(node.ref)

        for pattern, build_requires in build_requires.items():
            if ((node.recipe == RECIPE_CONSUMER and pattern == "&") or
                (node.recipe != RECIPE_CONSUMER and pattern == "&!") or
                    fnmatch.fnmatch(str_ref, pattern)):
                for build_require in build_requires:  # Do the override
                    # FIXME: converting back to string?
                    node.conanfile.requires.build_require(str(build_require))

    @staticmethod
    def _check_provides(dep_graph):
        for node in dep_graph.nodes:
            provides = {}
            for v in node.transitive_deps.values():
                if not v.node.conanfile.provides:
                    continue
                for provide in v.node.conanfile.provides:
                    new_req = v.require.copy()
                    new_req.ref = ConanFileReference(provide, new_req.ref.version, new_req.ref.user,
                                                     new_req.ref.channel, validate=False)
                    existing = node.transitive_deps.get(new_req)
                    if existing is not None:
                        node.conflict = (GraphError.PROVIDE_CONFLICT, [existing.node, v.node])
                        dep_graph.error = True
                        return
                    else:
                        existing_provide = provides.get(new_req)
                        if existing_provide is not None:
                            node.conflict = (GraphError.PROVIDE_CONFLICT, [existing_provide,
                                                                           v.node])
                            dep_graph.error = True
                            return
                        else:
                            provides[new_req] = v.node

    def _prepare_node(self, node, profile_host, profile_build, graph_lock, down_ref, down_options):
        if graph_lock:
            graph_lock.pre_lock_node(node)

        # basic node configuration: calling configure() and requirements()
        conanfile, ref = node.conanfile, node.ref

        run_configure_method(conanfile, down_options, down_ref, ref)

        # Update requirements (overwrites), computing new upstream
        if hasattr(conanfile, "requirements"):
            with conanfile_exception_formatter(str(conanfile), "requirements"):
                conanfile.requirements()

        # TODO: Maybe this could be integrated in one single requirements() method
        # Update requirements (overwrites), computing new upstream
        if hasattr(conanfile, "build_requirements"):
            with conanfile_exception_formatter(str(conanfile), "build_requirements"):
                # This calls "self.build_requires("")
                conanfile.build_requires = BuildRequirements(conanfile.requires)
                conanfile.test_requires = TestRequirements(conanfile.requires)
                conanfile.build_requirements()

        # Alias that are cached should be replaced here, bc next requires.update() will warn if not
        # TODO: self._resolve_cached_alias(node.conanfile.requires.values(), graph)

        self._add_profile_build_requires(node, profile_host, profile_build)
        if graph_lock:  # No need to evaluate, they are hardcoded in lockfile
            graph_lock.lock_node(node, node.conanfile.requires.values())

    def _expand_node(self, node, graph, check_updates, update,
                     remotes, profile_host, profile_build, graph_lock):

        print("Expanding node", node)

        # if there are version-ranges, resolve them before expanding each of the requirements
        # Resolve possible version ranges of the current node requirements
        # new_reqs is a shallow copy of what is propagated upstream, so changes done by the
        # RangeResolver are also done in new_reqs, and then propagated!

        # Add existing requires to the transitive_deps, so they are there for overrides
        for require in node.conanfile.requires.values():
            node.transitive_deps.set_empty(require)

        # Expand each one of the current requirements
        for require in node.conanfile.requires.values():
            # TODO: if require.override:
            #     continue
            self._expand_require(require, node, graph, check_updates, update, remotes,
                                 profile_host, profile_build,
                                 graph_lock)

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

    def _expand_require(self, require, node, graph, check_updates, update, remotes, profile_host,
                        profile_build, graph_lock, populate_settings_target=True):
        # Handle a requirement of a node. There are 2 possibilities
        #    node -(require)-> new_node (creates a new node in the graph)
        #    node -(require)-> previous (creates a diamond with a previously existing node)

        # TODO: allow bootstrapping, use references instead of names
        print("  Expanding require ", node, "->", require)
        # If the requirement is found in the node public dependencies, it is a diamond
        previous = node.check_downstream_exists(require)
        prev_node = None
        if previous:
            prev_require, prev_node, base_previous = previous
            print("  Existing previous requirements from ", base_previous, "=>", prev_require)

            if prev_require is None:  # Loop
                loop_node = Node(require.ref, None, context=prev_node.context)
                loop_node.conflict = GraphError.LOOP, prev_node
                graph.add_node(loop_node)
                graph.add_edge(node, loop_node, require)
                raise DepsGraphBuilder.StopRecursion("Loop found")

            if prev_node is None:  # Existing override
                print("  Require was an override from ", base_previous, "=", prev_require)
                print("  Require equality: \n", require, "\n", prev_require, "\n", prev_require == require)
                # TODO: resolve the override, version ranges, etc
                require = prev_require
            else:
                # self._resolve_cached_alias([require], graph)
                # As we are closing a diamond, there can be conflicts. This will raise if conflicts
                conflict = self._conflicting_references(prev_node, require.ref, node.ref)
                if conflict:  # It is possible to get conflict from alias, try to resolve it
                    result = self._resolve_recipe(node, graph, require.ref, check_updates,
                                                  update, remotes, profile_host, graph_lock)
                    _, dep_conanfile, recipe_status, _, _ = result
                    # Maybe it was an ALIAS, so we can check conflict again
                    conflict = self._conflicting_references(prev_node, require.ref, node.ref)
                    if conflict:
                        conflict_node = Node(require.ref, dep_conanfile, context=prev_node.context)
                        conflict_node.recipe = recipe_status
                        base_previous.conflict = GraphError.VERSION_CONFLICT, [prev_node,
                                                                               conflict_node]
                        graph.add_node(conflict_node)
                        graph.add_edge(node, conflict_node, require)
                        raise DepsGraphBuilder.StopRecursion("Unresolved reference")

        if prev_node is None:
            # new node, must be added and expanded (node -> new_node)
            if require.build:
                profile = profile_build
                context = CONTEXT_BUILD
            else:
                profile = profile_host if node.context == CONTEXT_HOST else profile_build
                context = node.context

            try:
                # TODO: If it is locked not resolve range
                #  if not require.locked_id:  # if it is locked, nothing to resolved
                # TODO: This range-resolve might resolve in a given remote or cache
                # Make sure next _resolve_recipe use it
                resolved_ref = self._resolver.resolve(require, str(node.ref), update, remotes)

                # This accounts for alias too
                resolved = self._resolve_recipe(node, graph, resolved_ref, check_updates, update,
                                                remotes, profile, graph_lock)
            except ConanException as e:
                error_node = Node(require.ref, conanfile=None, context=context)
                error_node.recipe = RECIPE_MISSING
                graph.add_node(error_node)
                graph.add_edge(node, error_node, require)
                raise DepsGraphBuilder.StopRecursion(str(e))

            new_ref, dep_conanfile, recipe_status, remote, locked_id = resolved
            new_node = self._create_new_node(node, dep_conanfile, require, new_ref, context,
                                             recipe_status, remote, locked_id, profile_host,
                                             profile_build, populate_settings_target)

            down_options = node.conanfile.options.deps_package_values
            self._prepare_node(new_node, profile_host, profile_build, graph_lock,
                               node.ref, down_options)

            require.compute_run(new_node)
            graph.add_node(new_node)
            graph.add_edge(node, new_node, require)
            if node.propagate_downstream(require, new_node):
                raise DepsGraphBuilder.StopRecursion("Conflict in runtime")

            # RECURSION, keep expanding (depth-first) the new node
            return self._expand_node(new_node, graph, check_updates,
                                     update, remotes, profile_host, profile_build, graph_lock)
        else:  # a public node already exist with this name
            print("Closing a loop from ", node, "=>", prev_node)
            require.compute_run(prev_node)
            graph.add_edge(node, prev_node, require)
            node.propagate_closing_loop(require, prev_node)

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

    def _resolve_recipe(self, current_node, dep_graph, ref, check_updates,
                        update, remotes, profile, graph_lock, original_ref=None):
        result = self._proxy.get_recipe(ref, check_updates, update, remotes)
        conanfile_path, recipe_status, remote, new_ref = result

        # TODO locked_id = requirement.locked_id
        locked_id = None
        lock_py_requires = graph_lock.python_requires(locked_id) if locked_id is not None else None
        dep_conanfile = self._loader.load_conanfile(conanfile_path, profile, ref=ref,
                                                    lock_python_requires=lock_py_requires)
        if recipe_status == RECIPE_EDITABLE:
            dep_conanfile.in_local_cache = False
            dep_conanfile.develop = True

        if getattr(dep_conanfile, "alias", None):
            new_ref_norev = new_ref.copy_clear_rev()
            pointed_ref = ConanFileReference.loads(dep_conanfile.alias)
            dep_graph.aliased[new_ref_norev] = pointed_ref  # Caching the alias
            if original_ref:  # So transitive alias resolve to the latest in the chain
                dep_graph.aliased[original_ref] = pointed_ref
            return self._resolve_recipe(current_node, dep_graph, pointed_ref, check_updates,
                                        update, remotes, profile, graph_lock, original_ref)

        return new_ref, dep_conanfile, recipe_status, remote, locked_id

    @staticmethod
    def _create_new_node(current_node, dep_conanfile, requirement, new_ref, context,
                         recipe_status, remote, locked_id, profile_host, profile_build,
                         populate_settings_target):

        # TODO: This should be out of here
        # If there is a context_switch, it is because it is a BR-build
        # Assign the profiles depending on the context
        dep_conanfile.settings_build = profile_build.processed_settings.copy()
        context_switch = (current_node.context == CONTEXT_HOST and requirement.build)
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

        new_node = Node(new_ref, dep_conanfile, context=context)
        new_node.revision_pinned = requirement.ref.revision is not None
        new_node.recipe = recipe_status
        new_node.remote = remote

        if locked_id is not None:
            new_node.id = locked_id

        return new_node
