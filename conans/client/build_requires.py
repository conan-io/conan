import copy
import fnmatch
from collections import OrderedDict

from conans.client.printer import Printer
from conans.errors import conanfile_exception_formatter
from conans.model.ref import ConanFileReference


def _apply_build_requires(deps_graph, conanfile):
    requires_nodes = deps_graph.direct_requires()
    for node in requires_nodes:
        conan_ref, build_require_conanfile = node

        conanfile.deps_cpp_info.update(build_require_conanfile.cpp_info, conan_ref.name)
        conanfile.deps_cpp_info.update_deps_cpp_info(build_require_conanfile.deps_cpp_info)

        conanfile.deps_env_info.update(build_require_conanfile.env_info, conan_ref.name)
        conanfile.deps_env_info.update_deps_env_info(build_require_conanfile.deps_env_info)

        conanfile.deps_user_info[conan_ref.name] = build_require_conanfile.user_info


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
    def __init__(self, loader, graph_builder, registry, output, profile_build_requires):
        self._loader = loader
        self._graph_builder = graph_builder
        self._output = output
        self._registry = registry
        # Do not alter the original
        self._profile_build_requires = copy.copy(profile_build_requires)

    @staticmethod
    def _get_recipe_build_requires(conanfile):
        conanfile.build_requires = _RecipeBuildRequires(conanfile)
        if hasattr(conanfile, "build_requirements"):
            with conanfile_exception_formatter(str(conanfile), "build_requirements"):
                conanfile.build_requirements()

        return conanfile.build_requires

    def install(self, reference, conanfile, installer):
        str_ref = str(reference)
        package_build_requires = self._get_recipe_build_requires(conanfile)
        for pattern, build_requires in self._profile_build_requires.items():
            if ((not str_ref and pattern == "&") or
                    (str_ref and pattern == "&!") or
                    fnmatch.fnmatch(str_ref, pattern)):
                package_build_requires.update(build_requires)

        if package_build_requires:
            self._output.info("Installing build requirements of: %s" % (str_ref or "PROJECT"))
            self._output.info("Build requires: [%s]"
                              % ", ".join(str(r) for r in package_build_requires.values()))
            # clear root package options, they won't match the build-require
            conanfile.build_requires_options.clear_unscoped_options()
            build_require_graph = self._install(package_build_requires.values(),
                                                conanfile.build_requires_options, installer)

            _apply_build_requires(build_require_graph, conanfile)
            self._output.info("Installed build requirements of: %s" % (str_ref or "PROJECT"))

    def _install(self, build_requires_references, build_requires_options, installer):
        # No need current path
        conanfile = self._loader.load_virtual(build_requires_references, None, scope_options=False,
                                              build_requires_options=build_requires_options)
        # compute and print the graph of transitive build-requires
        deps_graph = self._graph_builder.load(conanfile)
        Printer(self._output).print_graph(deps_graph, self._registry)

        # Make sure we recursively do not propagate the "*" pattern
        old_build_requires = self._profile_build_requires.copy()
        self._profile_build_requires.pop("*", None)
        self._profile_build_requires.pop("&!", None)

        installer.install(deps_graph, "")
        self._profile_build_requires = old_build_requires  # Restore original values
        return deps_graph
