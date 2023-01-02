import copy
from collections import deque

from conans.client.conanfile.configure import run_configure_method
from conans.client.graph.graph import DepsGraph, Node, CONTEXT_HOST, \
    CONTEXT_BUILD, TransitiveRequirement, RECIPE_VIRTUAL
from conans.client.graph.graph_error import GraphError
from conans.client.graph.profile_node_definer import initialize_conanfile_profile
from conans.client.graph.provides import check_graph_provides
from conans.errors import ConanException
from conans.model.options import Options
from conans.model.recipe_ref import RecipeReference, ref_matches
from conans.model.requires import Requirement


class DepsGraphBuilder(object):

    def __init__(self, proxy, loader, resolver, remotes, update, check_update):
        self._proxy = proxy
        self._loader = loader
        self._resolver = resolver
        self._remotes = remotes  # TODO: pass as arg to load_graph()
        self._update = update
        self._check_update = check_update

    def load_graph(self, root_node, profile_host, profile_build, graph_lock=None):
        assert profile_host is not None
        assert profile_build is not None
        assert isinstance(profile_host.options, Options)
        assert isinstance(profile_build.options, Options)
        # print("Loading graph")
        dep_graph = DepsGraph()

        # TODO: Why assign here the settings_build and settings_target?
        root_node.conanfile.settings_build = profile_build.processed_settings.copy()
        root_node.conanfile.settings_target = None

        self._prepare_node(root_node, profile_host, profile_build, Options())
        self._initialize_requires(root_node, dep_graph, graph_lock)
        dep_graph.add_node(root_node)

        open_requires = deque((r, root_node) for r in root_node.conanfile.requires.values())
        try:
            while open_requires:
                # Fetch the first waiting to be expanded (depth-first)
                (require, node) = open_requires.popleft()
                if require.override:
                    continue
                new_node = self._expand_require(require, node, dep_graph, profile_host,
                                                profile_build, graph_lock)
                if new_node:
                    self._initialize_requires(new_node, dep_graph, graph_lock)
                    open_requires.extendleft((r, new_node)
                                             for r in reversed(new_node.conanfile.requires.values()))
            self._remove_overrides(dep_graph)
            check_graph_provides(dep_graph)
        except GraphError as e:
            dep_graph.error = e
        dep_graph.resolved_ranges = self._resolver.resolved_ranges
        return dep_graph

    def _expand_require(self, require, node, graph, profile_host, profile_build, graph_lock):
        # Handle a requirement of a node. There are 2 possibilities
        #    node -(require)-> new_node (creates a new node in the graph)
        #    node -(require)-> previous (creates a diamond with a previously existing node)

        # TODO: allow bootstrapping, use references instead of names
        # print("  Expanding require ", node, "->", require)
        previous = node.check_downstream_exists(require)
        prev_node = None
        if previous is not None:
            prev_require, prev_node, base_previous = previous
            # print("  Existing previous requirements from ", base_previous, "=>", prev_require)

            if prev_require is None:
                raise GraphError.loop(node, require, prev_node)

            prev_ref = prev_node.ref if prev_node else prev_require.ref
            if prev_require.force or prev_require.override:  # override
                require.ref = prev_ref
            else:
                self._conflicting_version(require, node, prev_require, prev_node,
                                          prev_ref, base_previous)

        if prev_node is None:
            # new node, must be added and expanded (node -> new_node)
            new_node = self._create_new_node(node, require, graph, profile_host, profile_build,
                                             graph_lock)
            return new_node
        else:
            # print("Closing a loop from ", node, "=>", prev_node)
            require.process_package_type(node, prev_node)
            graph.add_edge(node, prev_node, require)
            node.propagate_closing_loop(require, prev_node)

    @staticmethod
    def _conflicting_version(require, node,
                             prev_require, prev_node, prev_ref, base_previous):
        version_range = require.version_range
        prev_version_range = prev_require.version_range if prev_node is None else None
        if version_range:
            # TODO: Check user/channel conflicts first
            if prev_version_range is not None:
                pass  # Do nothing, evaluate current as it were a fixed one
            else:
                if prev_ref.version in version_range:
                    require.ref = prev_ref
                else:
                    raise GraphError.conflict(node, require, prev_node, prev_require, base_previous)

        elif prev_version_range is not None:
            # TODO: CHeck user/channel conflicts first
            if require.ref.version not in prev_version_range:
                raise GraphError.conflict(node, require, prev_node, prev_require, base_previous)
        else:
            def _conflicting_refs(ref1, ref2):
                ref1_norev = copy.copy(ref1)
                ref1_norev.revision = None
                ref2_norev = copy.copy(ref2)
                ref2_norev.revision = None
                if ref2_norev != ref1_norev:
                    return True
                # Computed node, if is Editable, has revision=None
                # If new_ref.revision is None we cannot assume any conflict, user hasn't specified
                # a revision, so it's ok any previous_ref
                if ref1.revision and ref2.revision and ref1.revision != ref2.revision:
                    return True

            # As we are closing a diamond, there can be conflicts. This will raise if so
            conflict = _conflicting_refs(prev_ref, require.ref)
            if conflict:  # It is possible to get conflict from alias, try to resolve it
                raise GraphError.conflict(node, require, prev_node, prev_require, base_previous)

    @staticmethod
    def _prepare_node(node, profile_host, profile_build, down_options):

        # basic node configuration: calling configure() and requirements()
        conanfile, ref = node.conanfile, node.ref

        profile_options = profile_host.options if node.context == CONTEXT_HOST else profile_build.options
        assert isinstance(profile_options, Options), type(profile_options)
        run_configure_method(conanfile, down_options, profile_options, ref)

        # Apply build_tools_requires from profile, overriding the declared ones
        profile = profile_host if node.context == CONTEXT_HOST else profile_build
        tool_requires = profile.tool_requires
        for pattern, tool_requires in tool_requires.items():
            if ref_matches(ref, pattern, is_consumer=conanfile._conan_is_consumer):
                for tool_require in tool_requires:  # Do the override
                    if str(tool_require) == str(ref):  # FIXME: Ugly str comparison
                        continue  # avoid self-loop of build-requires in build context
                    # FIXME: converting back to string?
                    node.conanfile.requires.tool_require(str(tool_require),
                                                         raise_if_duplicated=False)

    def _initialize_requires(self, node, graph, graph_lock):
        # Introduce the current requires to define overrides
        # This is the first pass over one recipe requires
        if hasattr(node.conanfile, "python_requires"):
            graph.aliased.update(node.conanfile.python_requires.aliased)

        if graph_lock is not None:
            for require in node.conanfile.requires.values():
                graph_lock.resolve_locked(node, require)

        for require in node.conanfile.requires.values():
            self._resolve_alias(node, require, graph)
            node.transitive_deps[require] = TransitiveRequirement(require, node=None)

    def _resolve_alias(self, node, require, graph):
        alias = require.alias
        if alias is None:
            return

        # First try cached
        cached = graph.aliased.get(alias)
        if cached is not None:
            while True:
                new_cached = graph.aliased.get(cached)
                if new_cached is None:
                    break
                else:
                    cached = new_cached
            require.ref = cached
            return

        while alias is not None:
            # if not cached, then resolve
            try:
                result = self._proxy.get_recipe(alias, self._remotes, self._update,
                                                self._check_update)
                conanfile_path, recipe_status, remote, new_ref = result
            except ConanException as e:
                raise GraphError.missing(node, require, str(e))

            dep_conanfile = self._loader.load_basic(conanfile_path)
            try:
                pointed_ref = RecipeReference.loads(dep_conanfile.alias)
            except Exception as e:
                raise ConanException(f"Alias definition error in {alias}: {str(e)}")

            # UPDATE THE REQUIREMENT!
            require.ref = pointed_ref
            graph.aliased[alias] = pointed_ref  # Caching the alias
            new_req = Requirement(pointed_ref)  # FIXME: Ugly temp creation just for alias check
            alias = new_req.alias

    def _resolve_recipe(self, ref, graph_lock):
        result = self._proxy.get_recipe(ref, self._remotes, self._update, self._check_update)
        conanfile_path, recipe_status, remote, new_ref = result
        dep_conanfile = self._loader.load_conanfile(conanfile_path, ref=ref, graph_lock=graph_lock,
                                                    remotes=self._remotes, update=self._update,
                                                    check_update=self._check_update)
        return new_ref, dep_conanfile, recipe_status, remote

    def _create_new_node(self, node, require, graph, profile_host, profile_build, graph_lock):
        try:
            # TODO: If it is locked not resolve range
            #  if not require.locked_id:  # if it is locked, nothing to resolved
            # TODO: This range-resolve might resolve in a given remote or cache
            # Make sure next _resolve_recipe use it
            resolved_ref = self._resolver.resolve(require, str(node.ref), self._remotes,
                                                  self._update)

            # This accounts for alias too
            resolved = self._resolve_recipe(resolved_ref, graph_lock)
        except ConanException as e:
            raise GraphError.missing(node, require, str(e))

        new_ref, dep_conanfile, recipe_status, remote = resolved
        # If the node is virtual or a test package, the require is also "root"
        is_test_package = getattr(node.conanfile, "tested_reference_str", False)
        if node.conanfile._conan_is_consumer and (node.recipe == RECIPE_VIRTUAL or is_test_package):
            dep_conanfile._conan_is_consumer = True
        initialize_conanfile_profile(dep_conanfile, profile_build, profile_host, node.context,
                                     require.build, new_ref)

        context = CONTEXT_BUILD if require.build else node.context
        new_node = Node(new_ref, dep_conanfile, context=context, test=require.test)
        new_node.recipe = recipe_status
        new_node.remote = remote

        # The consumer "up_options" are the options that come from downstream to this node
        if require.options is not None:
            # If the consumer has specified "requires(options=xxx)", we need to use it
            # It will have less priority than downstream consumers
            down_options = Options(options_values=require.options)
            down_options.scope(new_ref)
            # At the moment, the behavior is the most restrictive one: default_options and
            # options["dep"].opt=value only propagate to visible and host dependencies
            # we will evaluate if necessary a potential "build_options", but recall that it is
            # now possible to do "self.build_requires(..., options={k:v})" to specify it
            if require.visible and context == CONTEXT_HOST:
                # Only visible requirements in the host context propagate options from downstream
                down_options.update_options(node.conanfile.up_options)
        else:
            down_options = node.conanfile.up_options if require.visible else Options()

        self._prepare_node(new_node, profile_host, profile_build, down_options)
        require.process_package_type(node, new_node)
        graph.add_node(new_node)
        graph.add_edge(node, new_node, require)
        if node.propagate_downstream(require, new_node):
            raise GraphError.runtime(node, new_node)

        # This is necessary to prevent infinite loops even when visibility is False
        ancestor = node.check_loops(new_node)
        if ancestor is not None:
            raise GraphError.loop(new_node, require, ancestor)

        return new_node

    @staticmethod
    def _remove_overrides(dep_graph):
        for node in dep_graph.nodes:
            to_remove = [r for r in node.transitive_deps if r.override]
            for r in to_remove:
                node.transitive_deps.pop(r)
