from conans.client.remote_registry import RemoteRegistry
from conans.client.printer import Printer
from conans.client.installer import ConanInstaller
from conans.model.build_info import DepsCppInfo
from conans.model.env_info import DepsEnvInfo
from collections import defaultdict
from conans.client.require_resolver import RequireResolver
from conans.client.deps_builder import DepsGraphBuilder
import fnmatch
import copy


def _apply_initial_deps_infos_to_conanfile(conanfile, initial_deps_infos):
    if not initial_deps_infos:
        return

    def apply_infos(infos):
        for build_dep_reference, info in infos.items():  # List of tuples (cpp_info, env_info)
            cpp_info, env_info = info
            conanfile.deps_cpp_info.update(cpp_info, build_dep_reference)
            conanfile.deps_env_info.update(env_info, build_dep_reference)

    # If there are some specific package-level deps infos apply them
    if conanfile.name and conanfile.name in initial_deps_infos.keys():
        apply_infos(initial_deps_infos[conanfile.name])

    # And also apply the global ones
    apply_infos(initial_deps_infos[None])


def _install_build_requires_and_get_infos(deps_graph, profile):
    # Build the graph and install the build_require dependency tree
    # Build a dict with
    # {"zlib": {"cmake/2.8@lasote/stable": (deps_cpp_info, deps_env_info),
    #           "other_tool/3.2@lasote/stable": (deps_cpp_info, deps_env_info)}
    #  "None": {"cmake/3.1@lasote/stable": (deps_cpp_info, deps_env_info)}
    # taking into account the package level requires
    refs_objects = {}
    requires_nodes = deps_graph.direct_requires()
    # We have all the cpp_info and env_info in the virtual conanfile, but we need those info objects at
    # requires level to filter later (profiles allow to filter targeting a library in the real deps tree)
    for node in requires_nodes:
        deps_cpp_info = DepsCppInfo()
        deps_cpp_info.public_deps = []  # FIXME: spaguetti
        deps_cpp_info.update(node.conanfile.cpp_info, node.conan_ref)
        deps_cpp_info.update(node.conanfile.deps_cpp_info, node.conan_ref)

        deps_env_info = DepsEnvInfo()
        deps_env_info.update(node.conanfile.env_info, node.conan_ref)
        deps_env_info.update(node.conanfile.deps_env_info, node.conan_ref)

        refs_objects[node.conan_ref] = (deps_cpp_info, deps_env_info)

    build_dep_infos = defaultdict(dict)
    for dest_package, references in profile.package_requires.items():  # Package level ones
        for ref in references:
            build_dep_infos[dest_package][ref] = refs_objects[ref]
    for global_reference in profile.requires:
        build_dep_infos[None][global_reference] = refs_objects[global_reference]

    return build_dep_infos


class BuildRequires(object):
    def __init__(self, loader, remote_proxy, output, client_cache, search_manager, build_requires,
                 current_path):
        self._remote_proxy = remote_proxy
        self._client_cache = client_cache
        self._output = output
        self._current_path = current_path
        self._loader = loader
        self._cached_graphs = {}
        self._search_manager = search_manager
        self._build_requires = build_requires

    def install(self, reference):
        build_requires = []
        str_ref = str(reference)
        for pattern, req_list in self._build_requires.items():
            if fnmatch.fnmatch(str_ref, pattern):
                build_requires.extend(req_list)
        if not build_requires:
            return
        self._output.info("%s: Build requires are: [%s]"
                          % (str(reference), ", ".join(str(r) for r in build_requires)))

        for build_require in build_requires:
            cached_graph = self._cached_graphs.get(build_require)
            if not cached_graph:
                cached_graph = self._install(build_require)
                self._cached_graphs[reference] = cached_graph

    def _install(self, build_require):
        self._output.info("Installing build_require: %s" % str(build_require))
        conanfile = self._loader.load_virtual(build_require, None)  # No need current path

        # FIXME: Forced update=True, build_mode, Where to define it?
        update = False
        build_modes = ["missing"]

        local_search = None if update else self._search_manager
        resolver = RequireResolver(self._output, local_search, self._remote_proxy)
        graph_builder = DepsGraphBuilder(self._remote_proxy, self._output, self._loader, resolver)
        deps_graph = graph_builder.load(conanfile)

        registry = RemoteRegistry(self._client_cache.registry, self._output)
        Printer(self._output).print_graph(deps_graph, registry)

        # Make sure we recursively do not propagate the "*" pattern
        build_requires = copy.copy(self)
        build_requires._build_requires.pop("*", None)

        installer = ConanInstaller(self._client_cache, self._output, self._remote_proxy,
                                   build_requires)
        installer.install(deps_graph, build_modes, self._current_path)
        self._output.info("Installed build_require: %s" % str(build_require))
        return deps_graph
