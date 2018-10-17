import os
import fnmatch
from collections import OrderedDict

from conans.model.ref import ConanFileReference
from conans.errors import conanfile_exception_formatter, ConanException
from conans.model.conan_file import get_env_context_manager
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.client.graph.graph_binaries import GraphBinariesAnalyzer
from conans.client.graph.graph import BINARY_BUILD, BINARY_WORKSPACE
from conans.client import settings_preprocessor
from conans.client.output import ScopedOutput
from conans.client.graph.build_mode import BuildMode
from conans.client.profile_loader import read_conaninfo_profile
from conans.paths import BUILD_INFO
from conans.util.files import load
from conans.client.generators.text import TXTGenerator
from conans.client.loader import ProcessedProfile


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
    def __init__(self, output, client_cache, registry, remote_manager, loader, proxy, resolver):
        self._proxy = proxy
        self._output = output
        self._resolver = resolver
        self._client_cache = client_cache
        self._registry = registry
        self._remote_manager = remote_manager
        self._loader = loader

    def load_consumer_conanfile(self, conanfile_path, info_folder, output,
                                deps_info_required=False):
        """loads a conanfile for local flow: source, imports, package, build
        """
        profile = read_conaninfo_profile(info_folder) or self._client_cache.default_profile
        cache_settings = self._client_cache.settings.copy()
        cache_settings.values = profile.settings_values
        # We are recovering state from captured profile from conaninfo, remove not defined
        cache_settings.remove_undefined()
        processed_profile = ProcessedProfile(cache_settings, profile, None)
        if conanfile_path.endswith(".py"):
            conanfile = self._loader.load_conanfile(conanfile_path, output, consumer=True, local=True,
                                                    processed_profile=processed_profile)
        else:
            conanfile = self._loader.load_conanfile_txt(conanfile_path, output, processed_profile)

        load_deps_info(info_folder, conanfile, required=deps_info_required)

        return conanfile

    def load_simple_graph(self, reference, profile, recorder):
        # Loads a graph without computing the binaries. It is necessary for
        # export-pkg command, not hitting the server
        # # https://github.com/conan-io/conan/issues/3432
        builder = DepsGraphBuilder(self._proxy, self._output, self._loader, self._resolver,
                                   workspace=None, recorder=recorder)
        cache_settings = self._client_cache.settings.copy()
        cache_settings.values = profile.settings_values
        settings_preprocessor.preprocess(cache_settings)
        processed_profile = ProcessedProfile(cache_settings, profile, create_reference=None)
        conanfile = self._loader.load_virtual([reference], processed_profile)
        graph = builder.load_graph(conanfile, check_updates=False, update=False, remote_name=None,
                                   processed_profile=processed_profile)
        return graph

    def load_graph(self, reference, create_reference, profile, build_mode, check_updates, update, remote_name,
                   recorder, workspace):

        def _inject_require(conanfile, reference):
            """ test_package functionality requires injecting the tested package as requirement
            before running the install
            """
            require = conanfile.requires.get(reference.name)
            if require:
                require.conan_reference = require.range_reference = reference
            else:
                conanfile.requires(str(reference))
            conanfile._conan_user = reference.user
            conanfile._conan_channel = reference.channel

        # Computing the full dependency graph
        cache_settings = self._client_cache.settings.copy()
        cache_settings.values = profile.settings_values
        settings_preprocessor.preprocess(cache_settings)
        processed_profile = ProcessedProfile(cache_settings, profile, create_reference)
        if isinstance(reference, list):  # Install workspace with multiple root nodes
            conanfile = self._loader.load_virtual(reference, processed_profile)
        elif isinstance(reference, ConanFileReference):
            # create without test_package and install <ref>
            conanfile = self._loader.load_virtual([reference], processed_profile)
        else:
            output = ScopedOutput("PROJECT", self._output)
            if reference.endswith(".py"):
                conanfile = self._loader.load_conanfile(reference, output, processed_profile, consumer=True)
                if create_reference:  # create with test_package
                    _inject_require(conanfile, create_reference)
            else:
                conanfile = self._loader.load_conanfile_txt(reference, output, processed_profile)

        build_mode = BuildMode(build_mode, self._output)
        deps_graph = self._load_graph(conanfile, check_updates, update,
                                      build_mode=build_mode, remote_name=remote_name,
                                      profile_build_requires=profile.build_requires,
                                      recorder=recorder, workspace=workspace,
                                      processed_profile=processed_profile)
        build_mode.report_matches()
        return deps_graph, conanfile, cache_settings

    @staticmethod
    def _get_recipe_build_requires(conanfile):
        conanfile.build_requires = _RecipeBuildRequires(conanfile)
        if hasattr(conanfile, "build_requirements"):
            with get_env_context_manager(conanfile):
                with conanfile_exception_formatter(str(conanfile), "build_requirements"):
                    conanfile.build_requirements()

        return conanfile.build_requires

    def _recurse_build_requires(self, graph, check_updates, update, build_mode, remote_name,
                                profile_build_requires, recorder, workspace, processed_profile):
        for node in list(graph.nodes):
            # Virtual conanfiles doesn't have output, but conanfile.py and conanfile.txt do
            # FIXME: To be improved and build a explicit model for this
            if node.conanfile.output is None:
                continue
            if node.binary not in (BINARY_BUILD, BINARY_WORKSPACE) and node.conan_ref:
                continue
            package_build_requires = self._get_recipe_build_requires(node.conanfile)
            str_ref = str(node.conan_ref or "")
            new_profile_build_requires = OrderedDict()
            profile_build_requires = profile_build_requires or {}
            for pattern, build_requires in profile_build_requires.items():
                if ((not str_ref and pattern == "&") or
                        (str_ref and pattern == "&!") or
                        fnmatch.fnmatch(str_ref, pattern)):
                            for build_require in build_requires:
                                if build_require.name in package_build_requires:  # Override existing
                                    package_build_requires[build_require.name] = build_require
                                else:  # Profile one
                                    new_profile_build_requires[build_require.name] = build_require

            if package_build_requires:
                node.conanfile.build_requires_options.clear_unscoped_options()
                virtual = self._loader.load_virtual(package_build_requires.values(), scope_options=False,
                                                    build_requires_options=node.conanfile.build_requires_options,
                                                    processed_profile=processed_profile)
                build_requires_package_graph = self._load_graph(virtual, check_updates, update, build_mode,
                                                                remote_name, profile_build_requires,
                                                                recorder, workspace, processed_profile)
                graph.add_graph(node, build_requires_package_graph, build_require=True)

            if new_profile_build_requires:
                node.conanfile.build_requires_options.clear_unscoped_options()
                virtual = self._loader.load_virtual(new_profile_build_requires.values(), scope_options=False,
                                                    build_requires_options=node.conanfile.build_requires_options,
                                                    processed_profile=processed_profile)

                build_requires_profile_graph = self._load_graph(virtual, check_updates, update, build_mode,
                                                                remote_name, new_profile_build_requires,
                                                                recorder, workspace, processed_profile)
                graph.add_graph(node, build_requires_profile_graph, build_require=True)

    def _load_graph(self, conanfile, check_updates, update, build_mode, remote_name,
                    profile_build_requires, recorder, workspace, processed_profile):
        builder = DepsGraphBuilder(self._proxy, self._output, self._loader, self._resolver, workspace, recorder)
        graph = builder.load_graph(conanfile, check_updates, update, remote_name, processed_profile)
        if build_mode is None:
            return graph
        binaries_analyzer = GraphBinariesAnalyzer(self._client_cache, self._output,
                                                  self._remote_manager, self._registry, workspace)
        binaries_analyzer.evaluate_graph(graph, build_mode, update, remote_name)

        self._recurse_build_requires(graph, check_updates, update, build_mode, remote_name,
                                     profile_build_requires, recorder, workspace, processed_profile)
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
