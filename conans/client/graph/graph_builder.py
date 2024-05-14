import copy

from collections import deque

from conan.internal.cache.conan_reference_layout import BasicLayout
from conans.client.conanfile.configure import run_configure_method
from conans.client.graph.graph import DepsGraph, Node, CONTEXT_HOST, \
    CONTEXT_BUILD, TransitiveRequirement, RECIPE_VIRTUAL
from conans.client.graph.graph import RECIPE_PLATFORM
from conans.client.graph.graph_error import GraphLoopError, GraphConflictError, GraphMissingError, \
    GraphRuntimeError, GraphError
from conans.client.graph.profile_node_definer import initialize_conanfile_profile
from conans.client.graph.provides import check_graph_provides
from conans.errors import ConanException
from conans.model.conan_file import ConanFile
from conans.model.options import Options, _PackageOptions
from conans.model.pkg_type import PackageType
from conans.model.recipe_ref import RecipeReference, ref_matches
from conans.model.requires import Requirement


class DepsGraphBuilder(object):

    def __init__(self, proxy, loader, resolver, cache, remotes, update, check_update, global_conf):
        self._proxy = proxy
        self._loader = loader
        self._resolver = resolver
        self._cache = cache
        self._remotes = remotes  # TODO: pass as arg to load_graph()
        self._update = update
        self._check_update = check_update
        self._resolve_prereleases = global_conf.get('core.version_ranges:resolve_prereleases')

    def load_graph(self, root_node, profile_host, profile_build, graph_lock=None):
        assert profile_host is not None
        assert profile_build is not None
        assert isinstance(profile_host.options, Options)
        assert isinstance(profile_build.options, Options)
        # print("Loading graph")
        dep_graph = DepsGraph()

        self._prepare_node(root_node, profile_host, profile_build, Options())
        self._initialize_requires(root_node, dep_graph, graph_lock, profile_build, profile_host)
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
                    self._initialize_requires(new_node, dep_graph, graph_lock, profile_build,
                                              profile_host)
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
                raise GraphLoopError(node, require, prev_node)

            prev_ref = prev_node.ref if prev_node else prev_require.ref
            if prev_require.force or prev_require.override:  # override
                require.overriden_ref = require.ref  # Store that the require has been overriden
                require.override_ref = prev_ref
                require.ref = prev_ref
            else:
                self._conflicting_version(require, node, prev_require, prev_node,
                                          prev_ref, base_previous, self._resolve_prereleases)

        if prev_node is None:
            # new node, must be added and expanded (node -> new_node)
            new_node = self._create_new_node(node, require, graph, profile_host, profile_build,
                                             graph_lock)
            return new_node
        else:
            # print("Closing a loop from ", node, "=>", prev_node)
            # Keep previous "test" status only if current is also test
            prev_node.test = prev_node.test and (node.test or require.test)
            self._save_options_conflicts(node, require, prev_node, graph)
            require.process_package_type(node, prev_node)
            graph.add_edge(node, prev_node, require)
            node.propagate_closing_loop(require, prev_node)

    def _save_options_conflicts(self, node, require, prev_node, graph):
        """ Store the discrepancies of options when closing a diamond, to later report
        them. This list is not exhaustive, only the diamond vertix, not other transitives
        """
        down_options = self._compute_down_options(node, require, prev_node.ref)
        down_options = down_options._deps_package_options  # noqa
        if not down_options:
            return
        down_pkg_options = _PackageOptions()
        for pattern, options in down_options.items():
            if ref_matches(prev_node.ref, pattern, is_consumer=False):
                down_pkg_options.update_options(options)
        prev_options = {k: v for k, v in prev_node.conanfile.options.items()}
        for k, v in down_pkg_options.items():
            prev_value = prev_options.get(k)
            if prev_value is not None and prev_value != v:
                d = graph.options_conflicts.setdefault(str(prev_node.ref), {})
                conflicts = d.setdefault(k, {"value": prev_value}).setdefault("conflicts", [])
                conflicts.append((node.ref, v))

    @staticmethod
    def _conflicting_version(require, node,
                             prev_require, prev_node, prev_ref, base_previous, resolve_prereleases):
        version_range = require.version_range
        prev_version_range = prev_require.version_range if prev_node is None else None
        if version_range:
            # TODO: Check user/channel conflicts first
            if prev_version_range is not None:
                # It it is not conflicting, but range can be incompatible, restrict range
                restricted_version_range = version_range.intersection(prev_version_range)
                if restricted_version_range is None:
                    raise GraphConflictError(node, require, prev_node, prev_require, base_previous)
                require.ref.version = restricted_version_range.version()
            else:
                if version_range.contains(prev_ref.version, resolve_prereleases):
                    require.ref = prev_ref
                else:
                    raise GraphConflictError(node, require, prev_node, prev_require, base_previous)

        elif prev_version_range is not None:
            # TODO: Check user/channel conflicts first
            if not prev_version_range.contains(require.ref.version, resolve_prereleases):
                raise GraphConflictError(node, require, prev_node, prev_require, base_previous)
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
                raise GraphConflictError(node, require, prev_node, prev_require, base_previous)

    @staticmethod
    def _prepare_node(node, profile_host, profile_build, down_options):

        # basic node configuration: calling configure() and requirements()
        conanfile, ref = node.conanfile, node.ref

        profile_options = profile_host.options if node.context == CONTEXT_HOST else profile_build.options
        assert isinstance(profile_options, Options), type(profile_options)
        run_configure_method(conanfile, down_options, profile_options, ref)

        # Apply build_tools_requires from profile, overriding the declared ones
        profile = profile_host if node.context == CONTEXT_HOST else profile_build
        for pattern, tool_requires in profile.tool_requires.items():
            if ref_matches(ref, pattern, is_consumer=conanfile._conan_is_consumer):
                for tool_require in tool_requires:  # Do the override
                    if str(tool_require) == str(ref):  # FIXME: Ugly str comparison
                        continue  # avoid self-loop of build-requires in build context
                    node.conanfile.requires.tool_require(tool_require.repr_notime(),
                                                         raise_if_duplicated=False)

    def _initialize_requires(self, node, graph, graph_lock, profile_build, profile_host):
        for require in node.conanfile.requires.values():
            alias = require.alias  # alias needs to be processed this early
            if alias is not None:
                resolved = False
                if graph_lock is not None:
                    resolved = graph_lock.replace_alias(require, alias)
                # if partial, we might still need to resolve the alias
                if not resolved:
                    self._resolve_alias(node, require, alias, graph)
            self._resolve_replace_requires(node, require, profile_build, profile_host, graph)
            node.transitive_deps[require] = TransitiveRequirement(require, node=None)

    def _resolve_alias(self, node, require, alias, graph):
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
                layout, recipe_status, remote = result
            except ConanException as e:
                raise GraphMissingError(node, require, str(e))

            conanfile_path = layout.conanfile()
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
        layout, recipe_status, remote = result
        conanfile_path = layout.conanfile()
        dep_conanfile = self._loader.load_conanfile(conanfile_path, ref=ref, graph_lock=graph_lock,
                                                    remotes=self._remotes, update=self._update,
                                                    check_update=self._check_update)
        return layout, dep_conanfile, recipe_status, remote

    @staticmethod
    def _resolved_system(node, require, profile_build, profile_host, resolve_prereleases):
        profile = profile_build if node.context == CONTEXT_BUILD else profile_host
        if node.context == CONTEXT_BUILD:
            # If we are in the build context, the platform_tool_requires ALSO applies to the
            # regular requires. It is not possible in the build context to have tool-requires
            # and regular requires to the same package from Conan and from Platform
            system_reqs = profile.platform_tool_requires
            if not require.build:
                system_reqs = system_reqs + profile.platform_requires
        else:
            system_reqs = profile.platform_tool_requires if require.build \
                else profile.platform_requires
        if system_reqs:
            version_range = require.version_range
            for d in system_reqs:
                if require.ref.name == d.name:
                    if version_range:
                        if version_range.contains(d.version, resolve_prereleases):
                            require.ref.version = d.version  # resolved range is replaced by exact
                            layout = BasicLayout(require.ref, None)
                            return layout, ConanFile(str(d)), RECIPE_PLATFORM, None
                    elif require.ref.version == d.version:
                        if d.revision is None or require.ref.revision is None or \
                                d.revision == require.ref.revision:
                            require.ref.revision = d.revision
                            layout = BasicLayout(require.ref, None)
                            return layout, ConanFile(str(d)), RECIPE_PLATFORM, None

    def _resolve_replace_requires(self, node, require, profile_build, profile_host, graph):
        profile = profile_build if node.context == CONTEXT_BUILD else profile_host
        replacements = profile.replace_tool_requires if require.build else profile.replace_requires
        if not replacements:
            return

        for pattern, alternative_ref in replacements.items():
            if pattern.name != require.ref.name:
                continue  # no match in name
            if pattern.version != "*":  # we need to check versions
                rrange = require.version_range
                valid = rrange.contains(pattern.version, self._resolve_prereleases) if rrange else \
                    require.ref.version == pattern.version
                if not valid:
                    continue
            if pattern.user != "*" and pattern.user != require.ref.user:
                continue
            if pattern.channel != "*" and pattern.channel != require.ref.channel:
                continue
            original_require = repr(require.ref)
            if alternative_ref.version != "*":
                require.ref.version = alternative_ref.version
            if alternative_ref.user != "*":
                require.ref.user = alternative_ref.user
            if alternative_ref.channel != "*":
                require.ref.channel = alternative_ref.channel
            if alternative_ref.revision != "*":
                require.ref.revision = alternative_ref.revision
            if require.ref.name != alternative_ref.name:  # This requires re-doing dict!
                node.conanfile.requires.reindex(require, alternative_ref.name)
            require.ref.name = alternative_ref.name
            graph.replaced_requires[original_require] = repr(require.ref)
            break  # First match executes the alternative and finishes checking others

    def _create_new_node(self, node, require, graph, profile_host, profile_build, graph_lock):
        require_version = str(require.ref.version)
        if require_version.startswith("<host_version") and require_version.endswith(">"):
            if not require.build or require.visible:
                raise ConanException(f"{node.ref} require '{require.ref}': 'host_version' can only "
                                     "be used for non-visible tool_requires")
            tracking_ref = require_version.split(':', 1)
            ref = require.ref
            if len(tracking_ref) > 1:
                ref = RecipeReference.loads(str(require.ref))
                ref.name = tracking_ref[1][:-1]  # Remove the trailing >
            req = Requirement(ref, headers=True, libs=True, visible=True)
            transitive = node.transitive_deps.get(req)
            if transitive is None or transitive.require.ref.user != ref.user \
                    or transitive.require.ref.channel != ref.channel:
                raise ConanException(f"{node.ref} require '{ref}': didn't find a matching "
                                     "host dependency")
            require.ref.version = transitive.require.ref.version

        resolved = self._resolved_system(node, require, profile_build, profile_host,
                                         self._resolve_prereleases)
        if graph_lock is not None:
            # Here is when the ranges and revisions are resolved
            graph_lock.resolve_locked(node, require, self._resolve_prereleases)

        if resolved is None:
            try:
                # TODO: If it is locked not resolve range
                # TODO: This range-resolve might resolve in a given remote or cache
                # Make sure next _resolve_recipe use it
                self._resolver.resolve(require, str(node.ref), self._remotes, self._update)
                resolved = self._resolve_recipe(require.ref, graph_lock)
            except ConanException as e:
                raise GraphMissingError(node, require, str(e))

        layout, dep_conanfile, recipe_status, remote = resolved

        new_ref = layout.reference
        dep_conanfile.folders.set_base_recipe_metadata(layout.metadata())  # None for platform_xxx
        # If the node is virtual or a test package, the require is also "root"
        is_test_package = getattr(node.conanfile, "tested_reference_str", False)
        if node.conanfile._conan_is_consumer and (node.recipe == RECIPE_VIRTUAL or is_test_package):
            dep_conanfile._conan_is_consumer = True
        initialize_conanfile_profile(dep_conanfile, profile_build, profile_host, node.context,
                                     require.build, new_ref, parent=node.conanfile)

        context = CONTEXT_BUILD if require.build else node.context
        new_node = Node(new_ref, dep_conanfile, context=context, test=require.test or node.test)
        new_node.recipe = recipe_status
        new_node.remote = remote

        down_options = self._compute_down_options(node, require, new_ref)

        if recipe_status != RECIPE_PLATFORM:
            self._prepare_node(new_node, profile_host, profile_build, down_options)
        if dep_conanfile.package_type is PackageType.CONF and node.recipe != RECIPE_VIRTUAL:
            raise ConanException(f"Configuration package {dep_conanfile} cannot be used as "
                                 f"requirement, but {node.ref} is requiring it")

        require.process_package_type(node, new_node)
        graph.add_node(new_node)
        graph.add_edge(node, new_node, require)
        if node.propagate_downstream(require, new_node):
            raise GraphRuntimeError(node, new_node)

        # This is necessary to prevent infinite loops even when visibility is False
        ancestor = node.check_loops(new_node)
        if ancestor is not None:
            raise GraphLoopError(new_node, require, ancestor)

        return new_node

    @staticmethod
    def _compute_down_options(node, require, new_ref):
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
            if require.visible:
                # Only visible requirements in the host context propagate options from downstream
                down_options.update_options(node.conanfile.up_options)
        else:
            if require.visible:
                down_options = node.conanfile.up_options
            elif not require.build:  # for requires in "host", like test_requires, pass myoptions
                down_options = node.conanfile.private_up_options
            else:
                down_options = Options(options_values=node.conanfile.default_build_options)
        return down_options

    @staticmethod
    def _remove_overrides(dep_graph):
        for node in dep_graph.nodes:
            to_remove = [r for r in node.transitive_deps if r.override]
            for r in to_remove:
                node.transitive_deps.pop(r)
