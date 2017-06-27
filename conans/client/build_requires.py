from conans.client.printer import Printer
import fnmatch
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
    def __init__(self, loader, graph_builder, registry, output, build_requires):
        self._loader = loader
        self._graph_builder = graph_builder
        self._output = output
        self._registry = registry
        self._build_requires = build_requires

    def _get_recipe_build_requires(self, conanfile):
        conanfile.build_requires = _RecipeBuildRequires(conanfile)
        if hasattr(conanfile, "build_requirements"):
            try:
                conanfile.build_requirements()
            except Exception as e:
                raise ConanException("Error in 'build_requirements()': %s" % str(e))
        return conanfile.build_requires

    def install(self, reference, conanfile, installer):
        str_ref = str(reference)
        package_build_requires = self._get_recipe_build_requires(conanfile)
        for pattern, build_requires in self._build_requires.items():
            if ((not str_ref and pattern == "&") or
                    (str_ref and pattern == "&!") or
                    fnmatch.fnmatch(str_ref, pattern)):
                package_build_requires.update(build_requires)

        if package_build_requires:
            self._output.info("Installing build requirements of: %s" % (str_ref or "PROJECT"))

            # clear root package options, they won't match the build-require
            conanfile.build_requires_options.clear_unscoped_options()
            build_require_graph = self._install(package_build_requires.values(),
                                                conanfile.build_requires_options, installer)

            _apply_build_requires(build_require_graph, conanfile)

    def _install(self, build_requires_references, build_requires_options, installer):
        self._output.info("Installing build requires: [%s]"
                          % ", ".join(str(r) for r in build_requires_references))
        # No need current path
        conanfile = self._loader.load_virtual(build_requires_references, None, scope_options=False,
                                              build_requires_options=build_requires_options)

        deps_graph = self._graph_builder.load(conanfile)
        Printer(self._output).print_graph(deps_graph, self._registry)

        # Make sure we recursively do not propagate the "*" pattern
        old_build_requires = self._build_requires.copy()
        self._build_requires.pop("*", None)
        self._build_requires.pop("&!", None)

        installer.install(deps_graph, "")
        self._build_requires = old_build_requires  # Restore original values
        self._output.info("Installed build requires: [%s]"
                          % ", ".join(str(r) for r in build_requires_references))
        return deps_graph
