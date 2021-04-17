import fnmatch
from collections import defaultdict

from conans.client.conanfile.configure import run_configure_method
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.compute_pid import compute_package_id
from conans.client.graph.graph import BINARY_BUILD, Node, CONTEXT_HOST, CONTEXT_BUILD
from conans.client.graph.graph_binaries import RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_EDITABLE, \
    BINARY_UNKNOWN
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.errors import ConanException
from conans.model.ref import ConanFileReference


class GraphManager(object):
    def __init__(self, output, cache, remote_manager, loader, proxy, resolver, binary_analyzer):
        self._proxy = proxy
        self._output = output
        self._resolver = resolver
        self._cache = cache
        self._remote_manager = remote_manager
        self._loader = loader
        self._binary_analyzer = binary_analyzer

    def load_consumer_conanfile(self, conanfile_path):
        """loads a conanfile for local flow: source
        """
        # This is very dirty, should be removed for Conan 2.0 (source() method only)
        profile_host = self._cache.default_profile
        profile_host.process_settings(self._cache)
        profile_build = None
        name, version, user, channel = None, None, None, None

        if conanfile_path.endswith(".py"):
            lock_python_requires = None
            conanfile = self._loader.load_consumer(conanfile_path,
                                                   profile_host=profile_host,
                                                   name=name, version=version,
                                                   user=user, channel=channel,
                                                   lock_python_requires=lock_python_requires)

            if profile_build:
                conanfile.settings_build = profile_build.processed_settings.copy()
                conanfile.settings_target = None

            run_configure_method(conanfile, down_options=None, down_ref=None, ref=None)
        else:
            conanfile = self._loader.load_conanfile_txt(conanfile_path, profile_host=profile_host)

        return conanfile

    def load_graph(self, reference, create_reference, profile_host, profile_build, graph_lock,
                   root_ref, build_mode, check_updates, update,
                   remotes, recorder, apply_build_requires=True, lockfile_node_id=None):
        """ main entry point to compute a full dependency graph
        """
        root_node = self._load_root_node(reference, create_reference, profile_host, graph_lock,
                                         root_ref, lockfile_node_id)
        deps_graph = self._resolve_graph(root_node, profile_host, profile_build, graph_lock,
                                         check_updates, update, remotes)
        # Run some validations once the graph is built
        #TODO: self._validate_graph_provides(deps_graph)
        return deps_graph

    def _load_root_node(self, reference, create_reference, profile_host, graph_lock, root_ref,
                        lockfile_node_id):
        """ creates the first, root node of the graph, loading or creating a conanfile
        and initializing it (settings, options) as necessary. Also locking with lockfile
        information
        """
        profile_host.dev_reference = create_reference  # Make sure the created one has develop=True

        if isinstance(reference, list):  # Install workspace with multiple root nodes
            conanfile = self._loader.load_virtual(reference, profile_host, scope_options=False)
            # Locking in workspaces not implemented yet
            return Node(ref=None, context=CONTEXT_HOST, conanfile=conanfile, recipe=RECIPE_VIRTUAL)

        # create (without test_package), install|info|graph|export-pkg <ref>
        if isinstance(reference, ConanFileReference):
            return self._load_root_direct_reference(reference, graph_lock, profile_host,
                                                    lockfile_node_id)

        path = reference  # The reference must be pointing to a user space conanfile
        if create_reference:  # Test_package -> tested reference
            return self._load_root_test_package(path, create_reference, graph_lock, profile_host)

        # It is a path to conanfile.py or conanfile.txt
        root_node = self._load_root_consumer(path, graph_lock, profile_host, root_ref)
        return root_node

    def _load_root_consumer(self, path, graph_lock, profile, ref):
        """ load a CONSUMER node from a user space conanfile.py or conanfile.txt
        install|info|create|graph <path>
        :path full path to a conanfile
        :graph_lock: might be None, information of lockfiles
        :profile: data to inject to the consumer node: settings, options
        :ref: previous reference of a previous command. Can be used for finding itself in
              the lockfile, or to initialize
        """
        if path.endswith(".py"):
            lock_python_requires = None
            if graph_lock:
                if ref.name is None:
                    # If the graph_info information is not there, better get what we can from
                    # the conanfile
                    # Using load_named() to run set_name() set_version() and get them
                    # so it can be found by name in the lockfile
                    conanfile = self._loader.load_named(path, None, None, None, None)
                    ref = ConanFileReference(ref.name or conanfile.name,
                                             ref.version or conanfile.version,
                                             ref.user, ref.channel, validate=False)
                node_id = graph_lock.get_consumer(ref)
                lock_python_requires = graph_lock.python_requires(node_id)

            conanfile = self._loader.load_consumer(path, profile,
                                                   name=ref.name,
                                                   version=ref.version,
                                                   user=ref.user,
                                                   channel=ref.channel,
                                                   lock_python_requires=lock_python_requires)

            ref = ConanFileReference(conanfile.name, conanfile.version,
                                     ref.user, ref.channel, validate=False)
            root_node = Node(ref, conanfile, context=CONTEXT_HOST, recipe=RECIPE_CONSUMER, path=path)
        else:
            conanfile = self._loader.load_conanfile_txt(path, profile, ref=ref)
            root_node = Node(None, conanfile, context=CONTEXT_HOST, recipe=RECIPE_CONSUMER,
                             path=path)

        if graph_lock:  # Find the Node ID in the lock of current root
            node_id = graph_lock.get_consumer(root_node.ref)
            root_node.id = node_id

        return root_node

    def _load_root_direct_reference(self, reference, graph_lock, profile, lockfile_node_id):
        """ When a full reference is provided:
        install|info|graph <ref> or export-pkg .
        :return a VIRTUAL root_node with a conanfile that requires the reference
        """
        conanfile = self._loader.load_virtual([reference], profile)
        root_node = Node(ref=None, conanfile=conanfile, context=CONTEXT_HOST, recipe=RECIPE_VIRTUAL)
        if graph_lock:  # Find the Node ID in the lock of current root
            graph_lock.find_require_and_lock(reference, conanfile, lockfile_node_id)
        return root_node

    def _load_root_test_package(self, path, create_reference, graph_lock, profile):
        """ when a test_package/conanfile.py is provided, together with the reference that is
        being created and need to be tested
        :return a CONSUMER root_node with a conanfile.py with an injected requires to the
        created reference
        """
        test = str(create_reference)
        # do not try apply lock_python_requires for test_package/conanfile.py consumer
        conanfile = self._loader.load_consumer(path, profile, user=create_reference.user,
                                               channel=create_reference.channel)
        conanfile.display_name = "%s (test package)" % str(test)
        conanfile.output.scope = conanfile.display_name
        # Injecting the tested reference
        require = conanfile.requires.get(create_reference.name)
        if require:
            require.ref = require.range_ref = create_reference
        else:
            conanfile.requires.add_ref(create_reference)
        ref = ConanFileReference(conanfile.name, conanfile.version,
                                 create_reference.user, create_reference.channel, validate=False)
        root_node = Node(ref, conanfile, recipe=RECIPE_CONSUMER, context=CONTEXT_HOST, path=path)
        if graph_lock:
            graph_lock.find_require_and_lock(create_reference, conanfile)
        return root_node

    def _resolve_graph(self, root_node, profile_host, profile_build, graph_lock,
                       check_updates, update, remotes):

        profile_host_build_requires = profile_host.build_requires
        builder = DepsGraphBuilder(self._proxy, self._output, self._loader, self._resolver)
        deps_graph = builder.load_graph(root_node, check_updates, update, remotes, profile_host,
                                        profile_build, graph_lock)
        version_ranges_output = self._resolver.output
        if version_ranges_output:
            self._output.success("Version ranges solved")
            for msg in version_ranges_output:
                self._output.info("    %s" % msg)
            self._output.writeln("")
            self._resolver.clear_output()

        for node in deps_graph.ordered_iterate():
            compute_package_id(node)

        return deps_graph

    def _recurse_build_requires(self, graph, builder, check_updates,
                                update, build_mode, remotes, profile_build_requires, recorder,
                                profile_host, profile_build, graph_lock, apply_build_requires=True,
                                nodes_subset=None, root=None):
        """
        :param graph: This is the full dependency graph with all nodes from all recursions
        """
        default_context = CONTEXT_BUILD if profile_build else CONTEXT_HOST
        self._binary_analyzer.evaluate_graph(graph, build_mode, update, remotes, nodes_subset, root)
        if not apply_build_requires:
            return

        for node in graph.ordered_iterate(nodes_subset):
            # Virtual conanfiles doesn't have output, but conanfile.py and conanfile.txt do
            # FIXME: To be improved and build a explicit model for this
            if node.recipe == RECIPE_VIRTUAL:
                continue
            # Packages with PACKAGE_ID_UNKNOWN might be built in the future, need build requires
            if (node.binary not in (BINARY_BUILD, BINARY_EDITABLE, BINARY_UNKNOWN)
                    and node.recipe != RECIPE_CONSUMER):
                continue
            package_build_requires = self._get_recipe_build_requires(node.conanfile, default_context)
            str_ref = str(node.ref)

            #  Compute the update of the current recipe build_requires when updated with the
            # downstream profile-defined build-requires
            new_profile_build_requires = []
            for pattern, build_requires in profile_build_requires.items():
                if ((node.recipe == RECIPE_CONSUMER and pattern == "&") or
                        (node.recipe != RECIPE_CONSUMER and pattern == "&!") or
                        fnmatch.fnmatch(str_ref, pattern)):
                    for build_require in build_requires:
                        br_key = (build_require.name, default_context)
                        if br_key in package_build_requires:  # Override defined
                            # this is a way to have only one package Name for all versions
                            # (no conflicts)
                            # but the dict key is not used at all
                            package_build_requires[br_key] = build_require
                        # Profile one or in different context
                        elif build_require.name != node.name or default_context != node.context:
                            new_profile_build_requires.append((build_require, default_context))

            def _recurse_build_requires(br_list, transitive_build_requires):
                nodessub = builder.extend_build_requires(graph, node, br_list, check_updates,
                                                         update, remotes, profile_host,
                                                         profile_build, graph_lock)
                self._recurse_build_requires(graph, builder, check_updates, update, build_mode,
                                             remotes, transitive_build_requires, recorder,
                                             profile_host, profile_build, graph_lock,
                                             nodes_subset=nodessub, root=node)

            if package_build_requires:
                if default_context == CONTEXT_BUILD:
                    br_build, br_host = [], []
                    for (_, ctxt), it in package_build_requires.items():
                        if ctxt == CONTEXT_BUILD:
                            br_build.append((it, ctxt))
                        else:
                            br_host.append((it, ctxt))
                    if br_build:
                        _recurse_build_requires(br_build, profile_build.build_requires)
                    if br_host:
                        _recurse_build_requires(br_host, profile_build_requires)
                else:
                    br_all = [(it, ctxt) for (_, ctxt), it in package_build_requires.items()]
                    _recurse_build_requires(br_all, profile_build_requires)

            if new_profile_build_requires:
                _recurse_build_requires(new_profile_build_requires, {})

            if graph_lock:
                graph_lock.check_locked_build_requires(node, package_build_requires,
                                                       new_profile_build_requires)

    @staticmethod
    def _validate_graph_provides(deps_graph):
        # Check that two different nodes are not providing the same (ODR violation)
        for node in deps_graph.nodes:
            provides = defaultdict(list)
            if node.conanfile.provides is not None:  # consumer conanfile doesn't initialize
                for it in node.conanfile.provides:
                    provides[it].append(node)

            for item in filter(lambda u: u.context == CONTEXT_HOST, node.public_closure):
                for it in item.conanfile.provides:
                    provides[it].append(item)

            # Check (and report) if any functionality is provided by several different recipes
            conflicts = [it for it, nodes in provides.items() if len(nodes) > 1]
            if conflicts:
                msg_lines = ["At least two recipes provides the same functionality:"]
                for it in conflicts:
                    nodes_str = "', '".join([n.conanfile.display_name for n in provides[it]])
                    msg_lines.append(" - '{}' provided by '{}'".format(it, nodes_str))
                raise ConanException('\n'.join(msg_lines))

    @staticmethod
    def _propagate_options(node):
        # TODO: USE
        # as this is the graph model
        conanfile = node.conanfile
        neighbors = node.neighbors()
        transitive_reqs = set()  # of PackageReference, avoid duplicates
        for neighbor in neighbors:
            ref, nconan = neighbor.ref, neighbor.conanfile
            transitive_reqs.add(neighbor.pref)
            transitive_reqs.update(nconan.info.requires.refs())

            conanfile.options.propagate_downstream(ref, nconan.info.full_options)
            # Update the requirements to contain the full revision. Later in lockfiles
            conanfile.requires[ref.name].ref = ref

        # There might be options that are not upstream, backup them, might be for build-requires
        conanfile.build_requires_options = conanfile.options.values
        conanfile.options.clear_unused(transitive_reqs)
        conanfile.options.freeze()


        self._propagate_options(node)

        # Make sure that locked options match
        if (node.graph_lock_node is not None and
            node.graph_lock_node.options is not None and
            node.conanfile.options.values != node.graph_lock_node.options):
            raise ConanException("{}: Locked options do not match computed options\n"
                                 "Locked options:\n{}\n"
                                 "Computed options:\n{}".format(node.ref,
                                                                node.graph_lock_node.options,
                                                                node.conanfile.options.values))

    """
        if hasattr(conanfile, "validate") and callable(conanfile.validate):
        with conanfile_exception_formatter(str(conanfile), "validate"):
            try:
                conanfile.validate()
            except ConanInvalidConfiguration as e:
                conanfile.info.invalid = str(e)
    """
