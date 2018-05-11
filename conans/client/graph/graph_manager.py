from conans.model.ref import ConanFileReference
from collections import OrderedDict
from conans.errors import conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager
import fnmatch
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.client.graph.graph_binaries import GraphBinariesAnalyzer


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
    def __init__(self, proxy, output, loader, resolver, client_cache, registry, remote_manager):
        self._proxy = proxy
        self._output = output
        self._loader = loader
        self._resolver = resolver
        self._client_cache = client_cache
        self._registry = registry
        self._remote_manager = remote_manager

    @staticmethod
    def _get_recipe_build_requires(conanfile):
        conanfile.build_requires = _RecipeBuildRequires(conanfile)
        if hasattr(conanfile, "build_requirements"):
            with get_env_context_manager(conanfile):
                with conanfile_exception_formatter(str(conanfile), "build_requirements"):
                    conanfile.build_requirements()

        return conanfile.build_requires

    def _recurse_build_requires(self, graph, check_updates, update, build_mode, remote_name,
                                profile_build_requires):
        for node in list(graph.nodes):
            if node.binary != "BUILD" and not node.conan_ref:
                continue

            privates = [r for r in node.conanfile.requires.values() if r.private]
            if privates:
                raise Exception("PRIVATES NOT IMPLEMENTED")
            package_build_requires = self._get_recipe_build_requires(node.conanfile)
            str_ref = str(node.conan_ref or "")
            new_profile_build_requires = OrderedDict()
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
                                                    build_requires_options=node.conanfile.build_requires_options)
                build_requires_package_graph = self.load_graph(virtual, check_updates, update, build_mode,
                                                               remote_name, package_build_requires)
                graph.add_graph(node, build_requires_package_graph)

            if new_profile_build_requires:
                node.conanfile.build_requires_options.clear_unscoped_options()
                virtual = self._loader.load_virtual(new_profile_build_requires.values(), scope_options=False,
                                                    build_requires_options=node.conanfile.build_requires_options)

                build_requires_profile_graph = self.load_graph(virtual, check_updates, update, build_mode,
                                                               remote_name, new_profile_build_requires)
                graph.add_graph(node, build_requires_profile_graph)

    def load_graph(self, conanfile, check_updates, update, build_mode, remote_name,
                   profile_build_requires):
        builder = DepsGraphBuilder(self._proxy, self._output, self._loader, self._resolver)
        graph = builder.load_graph(conanfile, check_updates, update)
        binaries_analyzer = GraphBinariesAnalyzer(self._client_cache, self._output,
                                                  self._remote_manager, self._registry)
        binaries_analyzer.evaluate_graph(graph, build_mode, update, remote_name)

        self._recurse_build_requires(graph, check_updates, update, build_mode, remote_name,
                                     profile_build_requires)
        return graph
