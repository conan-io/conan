from conans.client.remote_registry import RemoteRegistry
from conans.client.printer import Printer
from conans.client.installer import ConanInstaller
from conans.client.require_resolver import RequireResolver
from conans.client.deps_builder import DepsGraphBuilder
import fnmatch
import copy


def _apply_build_requires(deps_graph, conanfile):
    requires_nodes = deps_graph.direct_requires()
    for node in requires_nodes:
        conan_ref, build_require_conanfile = node

        conanfile.deps_cpp_info.update(build_require_conanfile.cpp_info, conan_ref.name)
        conanfile.deps_cpp_info.update_deps_cpp_info(build_require_conanfile.deps_cpp_info)

        conanfile.deps_env_info.update(build_require_conanfile.env_info, conan_ref.name)
        conanfile.deps_env_info.update_deps_env_info(build_require_conanfile.deps_env_info)


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

    def install(self, reference, conanfile):
        str_ref = str(reference)
        for pattern, build_requires in self._build_requires.items():
            if ((not str_ref and pattern == "&") or
                    (str_ref and pattern == "&!") or
                    fnmatch.fnmatch(str_ref, pattern)):
                self._output.info("%s: Build requires: [%s]"
                                  % (str(reference), ", ".join(str(r) for r in build_requires)))

                cached_graph = self._cached_graphs.get(pattern)
                if not cached_graph:
                    cached_graph = self._install(build_requires)
                    self._cached_graphs[pattern] = cached_graph

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
