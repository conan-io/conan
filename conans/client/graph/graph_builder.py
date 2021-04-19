import fnmatch
import time
from collections import OrderedDict

from conans.client.conanfile.configure import run_configure_method
from conans.client.graph.graph import DepsGraph, Node, RECIPE_EDITABLE, CONTEXT_HOST, CONTEXT_BUILD, \
    RECIPE_MISSING
from conans.errors import (ConanException, ConanExceptionInUserConanfileMethod,
                           conanfile_exception_formatter)
from conans.model.conan_file import get_env_context_manager
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirements, Requirement
from conans.util.log import logger


class _RecipeBuildRequires(OrderedDict):
    def __init__(self, conanfile, default_context):
        super(_RecipeBuildRequires, self).__init__()
        build_requires = getattr(conanfile, "build_requires", [])
        if not isinstance(build_requires, (list, tuple)):
            build_requires = [build_requires]
        self._default_context = default_context
        for build_require in build_requires:
            self.add(build_require, context=self._default_context)

    def add(self, build_require, context):
        if not isinstance(build_require, ConanFileReference):
            build_require = ConanFileReference.loads(build_require)
        self[(build_require.name, context)] = build_require

    def __call__(self, build_require, force_host_context=False):
        context = CONTEXT_HOST if force_host_context else self._default_context
        self.add(build_require, context)

    def __str__(self):
        items = ["{} ({})".format(br, ctxt) for (_, ctxt), br in self.items()]
        return ", ".join(items)


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

    def __init__(self, proxy, output, loader, resolver):
        self._proxy = proxy
        self._output = output
        self._loader = loader
        self._resolver = resolver

    def load_graph(self, root_node, check_updates, update, remotes, profile_host, profile_build,
                   graph_lock=None):
        check_updates = check_updates or update
        initial = graph_lock.initial_counter if graph_lock else None
        dep_graph = DepsGraph(initial_node_id=initial)
        if profile_build:
            root_node.conanfile.settings_build = profile_build.processed_settings.copy()
            root_node.conanfile.settings_target = None
        dep_graph.add_node(root_node)

        # enter recursive computation
        self._expand_node(root_node, dep_graph, Requirements(), None, None, check_updates,
                          update, remotes, profile_host, profile_build, graph_lock)

        return dep_graph

    def _expand_node(self, node, graph, down_reqs, down_ref, down_options, check_updates, update,
                     remotes, profile_host, profile_build, graph_lock):
        """ expands the dependencies of the node, recursively

        param node: Node object to be expanded in this step
        down_reqs: the Requirements as coming from downstream, which can overwrite current
                    values
        param down_ref: ConanFileReference of who is depending on current node for this expansion
        """
        # basic node configuration: calling configure() and requirements()
        if graph_lock:
            graph_lock.pre_lock_node(node)
        new_options = self._config_node(node, down_ref, down_options)

        # Alias that are cached should be replaced here, bc next requires.update() will warn if not
        # TODO: self._resolve_cached_alias(node.conanfile.requires.values(), graph)

        if graph_lock:  # No need to evaluate, they are hardcoded in lockfile
            graph_lock.lock_node(node, node.conanfile.requires.values())

        # propagation of requirements can be necessary if some nodes are not locked
        # OVERRIDES!!!
        node.conanfile.requires.override(down_reqs, self._output, node.ref, down_ref)
        # if there are version-ranges, resolve them before expanding each of the requirements
        # Resolve possible version ranges of the current node requirements
        # new_reqs is a shallow copy of what is propagated upstream, so changes done by the
        # RangeResolver are also done in new_reqs, and then propagated!
        conanfile = node.conanfile
        scope = conanfile.display_name
        #self._resolve_ranges(graph, conanfile.requires.values(), scope, update, remotes)
        # Expand each one of the current requirements
        for require in node.conanfile.requires:
            # TODO: if require.override:
            #     continue
            error = self._expand_require(require, node, graph, check_updates, update, remotes,
                                         profile_host, profile_build, new_options,
                                         graph_lock, context_switch=False)
            if error:
                return True

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
                        profile_build, new_options, graph_lock, context_switch,
                        populate_settings_target=True):
        # Handle a requirement of a node. There are 2 possibilities
        #    node -(require)-> new_node (creates a new node in the graph)
        #    node -(require)-> previous (creates a diamond with a previously existing node)

        # If the required is found in the node ancestors a loop is being closed
        context = CONTEXT_BUILD if context_switch else node.context
        name = require.ref.name  # TODO: allow bootstrapping, use references instead of names

        # If the requirement is found in the node public dependencies, it is a diamond
        previous = node.check_downstream_exists(require)

        if previous is None:
            # new node, must be added and expanded (node -> new_node)
            if context_switch:
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
            except ConanException:
                error_node = Node(require.ref, conanfile=None, context=context)
                error_node.recipe = RECIPE_MISSING
                graph.add_node(error_node)
                graph.add_edge(node, error_node, require)
                graph.error = True
                return False

            new_ref, dep_conanfile, recipe_status, remote, locked_id = resolved
            new_node = self._create_new_node(node, dep_conanfile, require, new_ref, context,
                                             recipe_status, remote, locked_id, profile_host,
                                             profile_build,
                                             context_switch, populate_settings_target)

            graph.add_node(new_node)
            graph.add_edge(node, new_node, require)
            node.propagate_downstream(require, new_node)

            override_reqs = node.get_override_reqs(new_node, require)

            # RECURSION, keep expanding (depth-first) the new node
            return self._expand_node(new_node, graph, override_reqs, node.ref, new_options,
                                     check_updates,
                                     update, remotes, profile_host, profile_build, graph_lock)
        else:  # a public node already exist with this name
            previous, base_previous = previous
            loop = previous == base_previous
            # self._resolve_cached_alias([require], graph)
            # As we are closing a diamond, there can be conflicts. This will raise if conflicts
            conflict = loop or self._conflicting_references(previous, require.ref, node.ref)
            if conflict:  # It is possible to get conflict from alias, try to resolve it
                result = self._resolve_recipe(node, graph, require.ref, check_updates,
                                              update, remotes, profile_host, graph_lock)
                _, dep_conanfile, recipe_status, _, _ = result
                # Maybe it was an ALIAS, so we can check conflict again
                conflict = loop or self._conflicting_references(previous, require.ref, node.ref)
                if conflict:
                    conflict_node = Node(require.ref, dep_conanfile, context=context)
                    conflict_node.recipe = recipe_status
                    conflict_node.conflict = previous
                    previous.conflict = conflict_node
                    graph.add_node(conflict_node)
                    graph.add_edge(node, conflict_node, require)
                    graph.error = True
                    return True

            graph.add_edge(node, previous, require)

            node.propagate_downstream(require, previous)
            for prev_relation, prev_node in previous.transitive_deps.items():
                # TODO: possibly optimize in a bulk propagate
                node.propagate_downstream_existing(prev_relation, prev_node)

            """# Recursion is only necessary if the inputs conflict with the current "previous"
            # configuration of upstream versions and options
            # recursion can stop if there is a graph_lock not relaxed
            lock_recurse = not (graph_lock and not graph_lock.relaxed)
            if lock_recurse and self._recurse(previous.public_closure, new_reqs, new_options,
                                              previous.context):
                self._expand_node(previous, graph, new_reqs, node.ref, new_options, check_updates,
                                  update, remotes, profile_host, profile_build, graph_lock)
            """

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

    @staticmethod
    def _config_node(node, down_ref, down_options):
        """ update settings and option in the current ConanFile, computing actual
        requirement values, cause they can be overridden by downstream requires
        param settings: dict of settings values => {"os": "windows"}
        """
        conanfile, ref = node.conanfile, node.ref

        run_configure_method(conanfile, down_options, down_ref, ref)

        # Update requirements (overwrites), computing new upstream
        if hasattr(conanfile, "requirements"):
            with conanfile_exception_formatter(str(conanfile), "requirements"):
                conanfile.requirements()

        new_options = conanfile.options.deps_package_values
        return new_options

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
            return self._resolve_recipe(current_node, dep_graph, ref, check_updates,
                                        update, remotes, profile, graph_lock, original_ref)

        return new_ref, dep_conanfile, recipe_status, remote, locked_id

    def _create_new_node(self, current_node, dep_conanfile, requirement, new_ref, context,
                         recipe_status, remote, locked_id, profile_host, profile_build,
                         context_switch, populate_settings_target):
        # If there is a context_switch, it is because it is a BR-build

        # Assign the profiles depending on the context
        if profile_build:  # Keep existing behavior (and conanfile members) if no profile_build
            dep_conanfile.settings_build = profile_build.processed_settings.copy()
            if not context_switch:
                if populate_settings_target:
                    # TODO: Check this, getting the settings from current doesn't seem right
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
