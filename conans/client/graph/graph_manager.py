import fnmatch
import os
from collections import OrderedDict

from conans.client.generators.text import TXTGenerator
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph import BINARY_BUILD, Node,\
    RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_EDITABLE
from conans.client.graph.graph_binaries import GraphBinariesAnalyzer
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.client.loader import ProcessedProfile
from conans.errors import ConanException, conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager
from conans.model.graph_info import GraphInfo
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
    def __init__(self, output, cache, remote_manager, loader, proxy, resolver):
        self._proxy = proxy
        self._output = output
        self._resolver = resolver
        self._cache = cache
        self._remote_manager = remote_manager
        self._loader = loader

    def load_consumer_conanfile(self, conanfile_path, info_folder,
                                deps_info_required=False, test=None):
        """loads a conanfile for local flow: source, imports, package, build
        """
        try:
            graph_info = GraphInfo.load(info_folder)
        except IOError:  # Only if file is missing
            # This is very dirty, should be removed for Conan 2.0 (source() method only)
            profile = self._cache.default_profile
            profile.process_settings(self._cache)
            name, version, user, channel = None, None, None, None
        else:
            name, version, user, channel, _ = graph_info.root
            profile = graph_info.profile
            profile.process_settings(self._cache, preprocess=False)
            # This is the hack of recovering the options from the graph_info
            profile.options.update(graph_info.options)
        processed_profile = ProcessedProfile(profile, None)
        if conanfile_path.endswith(".py"):
            conanfile = self._loader.load_consumer(conanfile_path,
                                                   processed_profile=processed_profile, test=test,
                                                   name=name, version=version,
                                                   user=user, channel=channel)
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
                   remote_name, recorder, apply_build_requires=True):

        def _inject_require(conanfile, ref):
            """ test_package functionality requires injecting the tested package as requirement
            before running the install
            """
            require = conanfile.requires.get(ref.name)
            if require:
                require.ref = require.range_ref = ref
            else:
                conanfile.requires(str(ref))
            conanfile._conan_user = ref.user
            conanfile._conan_channel = ref.channel

        # Computing the full dependency graph
        profile = graph_info.profile
        processed_profile = ProcessedProfile(profile, create_reference)
        ref = None
        if isinstance(reference, list):  # Install workspace with multiple root nodes
            conanfile = self._loader.load_virtual(reference, processed_profile,
                                                  scope_options=False)
            root_node = Node(ref, conanfile, recipe=RECIPE_VIRTUAL)
        elif isinstance(reference, ConanFileReference):
            if not self._cache.config.revisions_enabled and reference.revision is not None:
                raise ConanException("Revisions not enabled in the client, specify a "
                                     "reference without revision")
            # create without test_package and install <ref>
            conanfile = self._loader.load_virtual([reference], processed_profile)
            root_node = Node(ref, conanfile, recipe=RECIPE_VIRTUAL)
        else:
            path = reference
            if path.endswith(".py"):
                test = str(create_reference) if create_reference else None
                conanfile = self._loader.load_consumer(path, processed_profile, test=test,
                                                       name=graph_info.root.name,
                                                       version=graph_info.root.version,
                                                       user=graph_info.root.user,
                                                       channel=graph_info.root.channel)
                if create_reference:  # create with test_package
                    _inject_require(conanfile, create_reference)

                ref = ConanFileReference(conanfile.name, conanfile.version,
                                         conanfile._conan_user, conanfile._conan_channel,
                                         validate=False)
            else:
                conanfile = self._loader.load_conanfile_txt(path, processed_profile,
                                                            ref=graph_info.root)

            root_node = Node(ref, conanfile, recipe=RECIPE_CONSUMER)

        build_mode = BuildMode(build_mode, self._output)
        deps_graph = self._load_graph(root_node, check_updates, update,
                                      build_mode=build_mode, remote_name=remote_name,
                                      profile_build_requires=profile.build_requires,
                                      recorder=recorder,
                                      processed_profile=processed_profile,
                                      apply_build_requires=apply_build_requires)

        # THIS IS NECESSARY to store dependencies options in profile, for consumer
        # FIXME: This is a hack. Might dissapear if the graph for local commands is always recomputed
        graph_info.options = root_node.conanfile.options.values

        version_ranges_output = self._resolver.output
        if version_ranges_output:
            self._output.success("Version ranges solved")
            for msg in version_ranges_output:
                self._output.info("    %s" % msg)
            self._output.writeln("")

        build_mode.report_matches()
        return deps_graph, conanfile

    @staticmethod
    def _get_recipe_build_requires(conanfile):
        conanfile.build_requires = _RecipeBuildRequires(conanfile)
        if hasattr(conanfile, "build_requirements"):
            with get_env_context_manager(conanfile):
                with conanfile_exception_formatter(str(conanfile), "build_requirements"):
                    conanfile.build_requirements()

        return conanfile.build_requires

    def _recurse_build_requires(self, graph, builder, binaries_analyzer, check_updates, update,
                                build_mode, remote_name, profile_build_requires, recorder,
                                processed_profile, apply_build_requires=True):

        binaries_analyzer.evaluate_graph(graph, build_mode, update, remote_name)
        if not apply_build_requires:
            return
        for node in graph.ordered_iterate():
            # Virtual conanfiles doesn't have output, but conanfile.py and conanfile.txt do
            # FIXME: To be improved and build a explicit model for this
            if node.recipe == RECIPE_VIRTUAL:
                continue
            if (node.binary not in (BINARY_BUILD, BINARY_EDITABLE)
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
                                if build_require.name in package_build_requires:  # Override existing
                                    # this is a way to have only one package Name for all versions
                                    # (no conflicts)
                                    # but the dict key is not used at all
                                    package_build_requires[build_require.name] = build_require
                                elif build_require.name != node.name:  # Profile one
                                    new_profile_build_requires.append(build_require)

            if package_build_requires:
                subgraph = builder.extend_build_requires(graph, node,
                                                         package_build_requires.values(),
                                                         check_updates, update, remote_name,
                                                         processed_profile)
                self._recurse_build_requires(subgraph, builder, binaries_analyzer, check_updates,
                                             update, build_mode,
                                             remote_name, profile_build_requires, recorder,
                                             processed_profile)
                graph.nodes.update(subgraph.nodes)

            if new_profile_build_requires:
                subgraph = builder.extend_build_requires(graph, node, new_profile_build_requires,
                                                         check_updates, update, remote_name,
                                                         processed_profile)
                self._recurse_build_requires(subgraph, builder, binaries_analyzer, check_updates,
                                             update, build_mode,
                                             remote_name, {}, recorder,
                                             processed_profile)
                graph.nodes.update(subgraph.nodes)

    def _load_graph(self, root_node, check_updates, update, build_mode, remote_name,
                    profile_build_requires, recorder, processed_profile, apply_build_requires):

        assert isinstance(build_mode, BuildMode)
        builder = DepsGraphBuilder(self._proxy, self._output, self._loader, self._resolver,
                                   recorder)
        graph = builder.load_graph(root_node, check_updates, update, remote_name, processed_profile)
        binaries_analyzer = GraphBinariesAnalyzer(self._cache, self._output,
                                                  self._remote_manager)

        self._recurse_build_requires(graph, builder, binaries_analyzer, check_updates, update,
                                     build_mode, remote_name,
                                     profile_build_requires, recorder, processed_profile,
                                     apply_build_requires=apply_build_requires)

        # Sort of closures, for linking order
        inverse_levels = {n: i for i, level in enumerate(graph.inverse_levels()) for n in level}
        for node in graph.nodes:
            closure = node.public_closure
            closure.pop(node.name)
            node_order = list(closure.values())
            # List sort is stable, will keep the original order of the closure, but prioritize levels
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
