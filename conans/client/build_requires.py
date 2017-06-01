from conans.client.remote_registry import RemoteRegistry
from conans.client.printer import Printer
from conans.client.installer import ConanInstaller
from conans.client.require_resolver import RequireResolver
from conans.client.deps_builder import DepsGraphBuilder
import fnmatch
import copy
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from collections import OrderedDict


def _apply_build_requires(deps_graph, conanfile):
    requires_nodes = deps_graph.direct_requires()
    for node in requires_nodes:
        conan_ref, build_require_conanfile = node

        conanfile.deps_cpp_info.update(build_require_conanfile.cpp_info, conan_ref.name)
        conanfile.deps_cpp_info.update_deps_cpp_info(build_require_conanfile.deps_cpp_info)

        conanfile.deps_env_info.update(build_require_conanfile.env_info, conan_ref.name)
        conanfile.deps_env_info.update_deps_env_info(build_require_conanfile.deps_env_info)


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


class BuildRequires(object):
    def __init__(self, loader, remote_proxy, output, client_cache, search_manager, build_requires,
                 current_path, build_modes):
        self._remote_proxy = remote_proxy
        self._client_cache = client_cache
        self._output = output
        self._current_path = current_path
        self._loader = loader
        self._cached_graphs = {}
        self._search_manager = search_manager
        self._build_requires = build_requires
        self._build_modes = build_modes

    def _get_recipe_build_requires(self, conanfile):
        conanfile.build_requires = _RecipeBuildRequires(conanfile)
        if hasattr(conanfile, "build_requirements"):
            try:
                conanfile.build_requirements()
            except Exception as e:
                raise ConanException("Error in 'build_requirements()': %s" % str(e))
        return conanfile.build_requires

    def install(self, reference, conanfile):
        str_ref = str(reference)
        package_build_requires = self._get_recipe_build_requires(conanfile)
        for pattern, build_requires in self._build_requires.items():
            if ((not str_ref and pattern == "&") or
                    (str_ref and pattern == "&!") or
                    fnmatch.fnmatch(str_ref, pattern)):

                package_build_requires.update(build_requires)

        if package_build_requires:
            str_build_requires = str(package_build_requires)
            self._output.info("%s: Build requires: [%s]" % (str(reference), str_build_requires))

            cached_graph = self._cached_graphs.get(str_build_requires)
            if not cached_graph:
                cached_graph = self._install(package_build_requires.values())
                self._cached_graphs[str_build_requires] = cached_graph

            _apply_build_requires(cached_graph, conanfile)

    def _install(self, references):
        self._output.info("Installing build requires: [%s]"
                          % ", ".join(str(r) for r in references))
        conanfile = self._loader.load_virtual(references, None, scope_options=False)  # No need current path

        # FIXME: Forced update=True, build_mode, Where to define it?
        update = False

        local_search = None if update else self._search_manager
        resolver = RequireResolver(self._output, local_search, self._remote_proxy)
        graph_builder = DepsGraphBuilder(self._remote_proxy, self._output, self._loader, resolver)
        deps_graph = graph_builder.load(conanfile)

        registry = RemoteRegistry(self._client_cache.registry, self._output)
        Printer(self._output).print_graph(deps_graph, registry)

        # Make sure we recursively do not propagate the "*" pattern
        build_requires = copy.copy(self)
        build_requires._build_requires = self._build_requires.copy()
        build_requires._build_requires.pop("*", None)
        build_requires._build_requires.pop("&!", None)

        installer = ConanInstaller(self._client_cache, self._output, self._remote_proxy,
                                   build_requires)
        installer.install(deps_graph, self._build_modes, self._current_path)
        self._output.info("Installed build requires: [%s]"
                          % ", ".join(str(r) for r in references))
        return deps_graph
