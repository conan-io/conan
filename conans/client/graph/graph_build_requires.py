from conans.model.ref import ConanFileReference
from collections import OrderedDict
from conans.errors import conanfile_exception_formatter
from conans.model.conan_file import get_env_context_manager
import fnmatch


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


class GraphBuildRequires(object):
    def __init__(self, graph_builder):
        self._graph_builder = graph_builder
        pass

    @staticmethod
    def _get_recipe_build_requires(conanfile):
        conanfile.build_requires = _RecipeBuildRequires(conanfile)
        if hasattr(conanfile, "build_requirements"):
            with get_env_context_manager(conanfile):
                with conanfile_exception_formatter(str(conanfile), "build_requirements"):
                    conanfile.build_requirements()

        return conanfile.build_requires

    def compute(self, graph, profile_build_requires):
        for node in graph.nodes:
            if node.binary != "BUILD":
                continue

            package_build_requires = self._get_recipe_build_requires(node.conanfile)

            str_ref = str(node.conan_ref)
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
                                    
    def _get_graph(self, conanfile, build_requires):
        conanfile.build_requires_options.clear_unscoped_options()
        virtual = self._loader.load_virtual(build_requires.values(), scope_options=False,
                                            build_requires_options=conanfile.build_requires_options)

        # compute and print the graph of transitive build-requires
        deps_graph = self._graph_builder.load_graph(virtual, check_updates=False, update=update)
        return deps_graph

