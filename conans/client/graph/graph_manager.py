import fnmatch
import os
from collections import OrderedDict

from conans.client.generators.text import TXTGenerator
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph import BINARY_BUILD, Node, \
    RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_EDITABLE, BINARY_UNKNOWN
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.errors import ConanException, conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager
from conans.model.graph_info import GraphInfo
from conans.model.graph_lock import GraphLock, GraphLockFile
from conans.model.ref import ConanFileReference
from conans.paths import BUILD_INFO
from conans.util.files import load


class _RecipeBuildRequires(OrderedDict):
    def __init__(self, conanfile):
        super(_RecipeBuildRequires, self).__init__()
        build_requires = getattr(conanfile, "build_requires", [])
        if not isinstance(build_requires, (list, tuple)):
            build_requires = [build_requires]
        for build_require in build_requires:
            self.add(build_require)

    def add(self, build_require):
        if not isinstance(build_require, ConanFileReference):
            build_require = ConanFileReference.loads(build_require)
        self[build_require.name] = build_require

    def __call__(self, build_require):
        self.add(build_require)

    def update(self, build_requires):
        for build_require in build_requires:
            self.add(build_require)

    def __str__(self):
        return ", ".join(str(r) for r in self.values())


class GraphManager(object):
    def __init__(self, output, cache, remote_manager, loader, proxy, resolver, binary_analyzer):
        self._proxy = proxy
        self._output = output
        self._resolver = resolver
        self._cache = cache
        self._remote_manager = remote_manager
        self._loader = loader
        self._binary_analyzer = binary_analyzer

    def load_consumer_conanfile(self, conanfile_path, info_folder,
                                deps_info_required=False, test=False):
        """loads a conanfile for local flow: source, imports, package, build
        """
        try:
            graph_info = GraphInfo.load(info_folder)
            graph_lock_file = GraphLockFile.load(info_folder, self._cache.config.revisions_enabled)
            graph_lock = graph_lock_file.graph_lock
            self._output.info("Using lockfile: '{}/conan.lock'".format(info_folder))
            profile = graph_lock_file.profile
            self._output.info("Using cached profile from lockfile")
        except IOError:  # Only if file is missing
            graph_lock = None
            # This is very dirty, should be removed for Conan 2.0 (source() method only)
            profile = self._cache.default_profile
            profile.process_settings(self._cache)
            name, version, user, channel = None, None, None, None
        else:
            name, version, user, channel, _ = graph_info.root
            profile.process_settings(self._cache, preprocess=False)
            # This is the hack of recovering the options from the graph_info
            profile.options.update(graph_info.options)
        processed_profile = profile
        if conanfile_path.endswith(".py"):
            lock_python_requires = None
            if graph_lock and not test:  # Only lock python requires if it is not test_package
                node_id = graph_lock.get_node(graph_info.root)
                lock_python_requires = graph_lock.python_requires(node_id)
            conanfile = self._loader.load_consumer(conanfile_path,
                                                   processed_profile=processed_profile,
                                                   name=name, version=version,
                                                   user=user, channel=channel,
                                                   lock_python_requires=lock_python_requires)
            if test:
                conanfile.display_name = "%s (test package)" % str(test)
                conanfile.output.scope = conanfile.display_name
            with get_env_context_manager(conanfile, without_python=True):
                with conanfile_exception_formatter(str(conanfile), "config_options"):
                    conanfile.config_options()
                with conanfile_exception_formatter(str(conanfile), "configure"):
                    conanfile.configure()

                conanfile.settings.validate()  # All has to be ok!
                conanfile.options.validate()
        else:
            conanfile = self._loader.load_conanfile_txt(conanfile_path, processed_profile)

        load_deps_info(info_folder, conanfile, required=deps_info_required)

        return conanfile

    def load_graph(self, reference, create_reference, graph_info, build_mode, check_updates, update,
                   remotes, recorder, apply_build_requires=True):
        root_node = self.load_root_node(reference, create_reference, graph_info)
        return self.resolve_graph(root_node, graph_info, build_mode, check_updates, update, remotes,
                                  recorder, apply_build_requires=apply_build_requires)

    def load_root_node(self, reference, create_reference, graph_info):
        profile = graph_info.profile
        profile.dev_reference = create_reference

        graph_lock = graph_info.graph_lock
        if isinstance(reference, list):  # Install workspace with multiple root nodes
            conanfile = self._loader.load_virtual(reference, profile, scope_options=False)
            # Locking in workspaces not implemented yet
            return Node(ref=None, conanfile=conanfile, recipe=RECIPE_VIRTUAL)

        # create (without test_package), install|info|graph|export-pkg <ref>
        if isinstance(reference, ConanFileReference):
            if not self._cache.config.revisions_enabled and reference.revision is not None:
                raise ConanException("Revisions not enabled in the client, specify a "
                                     "reference without revision")

            conanfile = self._loader.load_virtual([reference], profile)
            root_node = Node(ref=None, conanfile=conanfile, recipe=RECIPE_VIRTUAL)
            if graph_lock:  # Find the Node ID in the lock of current root
                node_id = graph_lock.get_node(reference)
                locked_ref = graph_lock._nodes[node_id].pref.ref
                conanfile.requires[reference.name].lock(locked_ref, node_id)
            return root_node

        if create_reference:  # Test_package -> tested reference
            path = reference
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
                                     conanfile._conan_user, conanfile._conan_channel,
                                     validate=False)
            root_node = Node(ref, conanfile, recipe=RECIPE_CONSUMER, path=path)
            if graph_lock:
                node_id = graph_lock.get_node(create_reference)
                locked_ref = graph_lock._nodes[node_id].pref.ref
                conanfile.requires[create_reference.name].lock(locked_ref, node_id)
            return root_node

        # It is a path to conanfile.py or conanfile.txt
        path = reference
        if path.endswith(".py"):
            lock_python_requires = None
            if graph_lock:
                if graph_info.root.name is None:
                    # If the graph_info information is not there, better get what we can from
                    # the conanfile
                    conanfile = self._loader.load_basic(path)
                    graph_info.root = ConanFileReference(graph_info.root.name or conanfile.name,
                                                         graph_info.root.version or conanfile.version,
                                                         graph_info.root.user,
                                                         graph_info.root.channel, validate=False)
                node_id = graph_lock.get_node(graph_info.root)
                lock_python_requires = graph_lock.python_requires(node_id)

            conanfile = self._loader.load_consumer(path, profile,
                                                   name=graph_info.root.name,
                                                   version=graph_info.root.version,
                                                   user=graph_info.root.user,
                                                   channel=graph_info.root.channel,
                                                   lock_python_requires=lock_python_requires)

            ref = ConanFileReference(conanfile.name, conanfile.version,
                                     conanfile._conan_user, conanfile._conan_channel,
                                     validate=False)
            root_node = Node(ref, conanfile, recipe=RECIPE_CONSUMER, path=path)
        else:
            conanfile = self._loader.load_conanfile_txt(path, profile, ref=graph_info.root)
            root_node = Node(None, conanfile, recipe=RECIPE_CONSUMER, path=path)

        if graph_lock:  # Find the Node ID in the lock of current root
            node_id = graph_lock.get_node(root_node.ref)
            root_node.id = node_id

        return root_node

    def resolve_graph(self, root_node, graph_info, build_mode, check_updates,
                      update, remotes, recorder, apply_build_requires=True):
        build_mode = BuildMode(build_mode, self._output)
        profile = graph_info.profile
        graph_lock = graph_info.graph_lock
        deps_graph = self._load_graph(root_node, check_updates, update,
                                      build_mode=build_mode, remotes=remotes,
                                      profile_build_requires=profile.build_requires,
                                      recorder=recorder,
                                      processed_profile=profile,
                                      apply_build_requires=apply_build_requires,
                                      graph_lock=graph_lock)

        # THIS IS NECESSARY to store dependencies options in profile, for consumer
        # FIXME: This is a hack. Might dissapear if graph for local commands is always recomputed
        graph_info.options = root_node.conanfile.options.values
        if root_node.ref:
            graph_info.root = root_node.ref
        if graph_info.graph_lock is None:
            graph_info.graph_lock = GraphLock(deps_graph)
        else:
            graph_info.graph_lock.update_check_graph(deps_graph, self._output)

        version_ranges_output = self._resolver.output
        if version_ranges_output:
            self._output.success("Version ranges solved")
            for msg in version_ranges_output:
                self._output.info("    %s" % msg)
            self._output.writeln("")

        build_mode.report_matches()
        return deps_graph

    @staticmethod
    def _get_recipe_build_requires(conanfile):
        conanfile.build_requires = _RecipeBuildRequires(conanfile)
        if hasattr(conanfile, "build_requirements"):
            with get_env_context_manager(conanfile):
                with conanfile_exception_formatter(str(conanfile), "build_requirements"):
                    conanfile.build_requirements()

        return conanfile.build_requires

    def _recurse_build_requires(self, graph, builder, check_updates,
                                update, build_mode, remotes, profile_build_requires, recorder,
                                processed_profile, graph_lock, apply_build_requires=True,
                                nodes_subset=None, root=None):
        """
        :param graph: This is the full dependency graph with all nodes from all recursions
        :param subgraph: A partial graph of the nodes that need to be evaluated and expanded
            at this recursion. Only the nodes belonging to this subgraph will get their package_id
            computed, and they will resolve build_requires if they need to be built from sources
        """

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
            package_build_requires = self._get_recipe_build_requires(node.conanfile)
            str_ref = str(node.ref)
            new_profile_build_requires = []
            profile_build_requires = profile_build_requires or {}
            for pattern, build_requires in profile_build_requires.items():
                if ((node.recipe == RECIPE_CONSUMER and pattern == "&") or
                        (node.recipe != RECIPE_CONSUMER and pattern == "&!") or
                        fnmatch.fnmatch(str_ref, pattern)):
                    for build_require in build_requires:
                        if build_require.name in package_build_requires:  # Override defined
                            # this is a way to have only one package Name for all versions
                            # (no conflicts)
                            # but the dict key is not used at all
                            package_build_requires[build_require.name] = build_require
                        elif build_require.name != node.name:  # Profile one
                            new_profile_build_requires.append(build_require)

            if package_build_requires:
                nodessub = builder.extend_build_requires(graph, node,
                                                         package_build_requires.values(),
                                                         check_updates, update, remotes,
                                                         processed_profile, graph_lock)

                self._recurse_build_requires(graph, builder,
                                             check_updates, update, build_mode,
                                             remotes, profile_build_requires, recorder,
                                             processed_profile, graph_lock, nodes_subset=nodessub,
                                             root=node)

            if new_profile_build_requires:
                nodessub = builder.extend_build_requires(graph, node, new_profile_build_requires,
                                                         check_updates, update, remotes,
                                                         processed_profile, graph_lock)

                self._recurse_build_requires(graph, builder,
                                             check_updates, update, build_mode,
                                             remotes, {}, recorder,
                                             processed_profile, graph_lock, nodes_subset=nodessub,
                                             root=node)

    def _load_graph(self, root_node, check_updates, update, build_mode, remotes,
                    profile_build_requires, recorder, processed_profile, apply_build_requires,
                    graph_lock):

        assert isinstance(build_mode, BuildMode)
        builder = DepsGraphBuilder(self._proxy, self._output, self._loader, self._resolver,
                                   recorder)
        graph = builder.load_graph(root_node, check_updates, update, remotes, processed_profile,
                                   graph_lock)

        self._recurse_build_requires(graph, builder, check_updates, update, build_mode,
                                     remotes, profile_build_requires, recorder, processed_profile,
                                     graph_lock, apply_build_requires=apply_build_requires)

        # Sort of closures, for linking order
        inverse_levels = {n: i for i, level in enumerate(graph.inverse_levels()) for n in level}
        for node in graph.nodes:
            closure = node.public_closure
            closure.pop(node.name)
            node_order = list(closure.values())
            # List sort is stable, will keep the original order of closure, but prioritize levels
            node_order.sort(key=lambda n: inverse_levels[n])
            node.public_closure = node_order

        return graph


def load_deps_info(current_path, conanfile, required):

    def get_forbidden_access_object(field_name):
        class InfoObjectNotDefined(object):
            def __getitem__(self, item):
                raise ConanException("self.%s not defined. If you need it for a "
                                     "local command run 'conan install'" % field_name)
            __getattr__ = __getitem__

        return InfoObjectNotDefined()

    if not current_path:
        return
    info_file_path = os.path.join(current_path, BUILD_INFO)
    try:
        deps_cpp_info, deps_user_info, deps_env_info = TXTGenerator.loads(load(info_file_path))
        conanfile.deps_cpp_info = deps_cpp_info
        conanfile.deps_user_info = deps_user_info
        conanfile.deps_env_info = deps_env_info
    except IOError:
        if required:
            raise ConanException("%s file not found in %s\nIt is required for this command\n"
                                 "You can generate it using 'conan install'"
                                 % (BUILD_INFO, current_path))
        conanfile.deps_cpp_info = get_forbidden_access_object("deps_cpp_info")
        conanfile.deps_user_info = get_forbidden_access_object("deps_user_info")
    except ConanException:
        raise ConanException("Parse error in '%s' file in %s" % (BUILD_INFO, current_path))
