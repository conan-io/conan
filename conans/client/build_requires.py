import copy
import fnmatch
from collections import OrderedDict

from conans.client.printer import Printer
from conans.errors import conanfile_exception_formatter
from conans.model.ref import ConanFileReference
from conans.model.conan_file import get_env_context_manager


def _apply_build_requires(deps_graph, conanfile, package_build_requires):
    requires_nodes = deps_graph.direct_requires()
    requires_nodes_dict = {}
    for node in requires_nodes:
        requires_nodes_dict[node.conan_ref.name] = node.conanfile

    # To guarantee that we respect the order given by the user, not the one imposed by the graph
    build_requires = []
    for package_name in package_build_requires:
        try:
            build_requires.append((package_name, requires_nodes_dict[package_name]))
        except KeyError:
            pass

    for package_name, build_require_conanfile in build_requires:
        conanfile.deps_cpp_info.update(build_require_conanfile.cpp_info, package_name)
        conanfile.deps_cpp_info.update_deps_cpp_info(build_require_conanfile.deps_cpp_info)

        conanfile.deps_env_info.update(build_require_conanfile.env_info, package_name)
        conanfile.deps_env_info.update_deps_env_info(build_require_conanfile.deps_env_info)

        conanfile.deps_user_info[package_name] = build_require_conanfile.user_info


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
    def __init__(self, loader, graph_builder, registry):
        self._loader = loader
        self._graph_builder = graph_builder
        self._registry = registry

    @staticmethod
    def _get_recipe_build_requires(conanfile):
        conanfile.build_requires = _RecipeBuildRequires(conanfile)
        if hasattr(conanfile, "build_requirements"):
            with get_env_context_manager(conanfile):
                with conanfile_exception_formatter(str(conanfile), "build_requirements"):
                    conanfile.build_requirements()

        return conanfile.build_requires

    def install(self, reference, conanfile, installer, profile_build_requires, output):
        str_ref = str(reference)
        package_build_requires = self._get_recipe_build_requires(conanfile)

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

        self._install(conanfile, reference, package_build_requires, installer, profile_build_requires, output)
        self._install(conanfile, reference, new_profile_build_requires, installer, profile_build_requires,
                      output, discard=True)

    def _install(self, conanfile, reference, build_requires, installer, profile_build_requires, output,
                 discard=False):
        if isinstance(reference, ConanFileReference):
            build_requires.pop(reference.name, None)
        if not build_requires:
            return
        if discard:
            profile_build_requires = copy.copy(profile_build_requires)
            profile_build_requires.pop("*", None)
            profile_build_requires.pop("&!", None)

        reference = str(reference)
        output.info("Installing build requirements of: %s" % (reference or "PROJECT"))
        output.info("Build requires: [%s]" % ", ".join(str(r) for r in build_requires.values()))
        # clear root package options, they won't match the build-require
        conanfile.build_requires_options.clear_unscoped_options()
        virtual = self._loader.load_virtual(build_requires.values(), scope_options=False,
                                            build_requires_options=conanfile.build_requires_options)

        # compute and print the graph of transitive build-requires
        deps_graph = self._graph_builder.load(virtual)
        Printer(output).print_graph(deps_graph, self._registry)
        # install them, recursively
        installer.install(deps_graph, profile_build_requires)
        _apply_build_requires(deps_graph, conanfile, build_requires)
        output.info("Installed build requirements of: %s" % (reference or "PROJECT"))
