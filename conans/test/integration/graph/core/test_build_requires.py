from parameterized import parameterized

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest
from conans.test.utils.tools import GenConanfile


class BuildRequiresGraphTest(GraphManagerTest):

    @parameterized.expand([("recipe", ), ("profile", )])
    def test_basic_build_require(self, build_require):
        # app -(br)-> tool0.1
        tool_ref = ConanFileReference.loads("tool/0.1@user/testing")
        self._cache_recipe(tool_ref, GenConanfile().with_name("tool").with_version("0.1"))
        if build_require == "recipe":
            deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                        .with_build_requires(tool_ref))
        else:
            profile_build_requires = {"*": [ConanFileReference.loads("tool/0.1@user/testing")]}
            deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1"),
                                          profile_build_requires=profile_build_requires)

        # Build requires always apply to the consumer
        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        tool = app.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[], build_deps=[tool], dependents=[],
                         closure=[tool])
        self._check_node(tool, "tool/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[app], closure=[])

    def test_transitive_build_require_recipe(self):
        # app -> lib -(br)-> tool
        tool_ref = ConanFileReference.loads("tool/0.1@user/testing")
        lib_ref = ConanFileReference.loads("lib/0.1@user/testing")

        self._cache_recipe(tool_ref, GenConanfile().with_name("tool").with_version("0.1"))
        self._cache_recipe(lib_ref, GenConanfile().with_name("lib").with_version("0.1")
                                                  .with_build_requires(tool_ref))
        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(lib_ref))

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        tool = lib.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], build_deps=[], dependents=[],
                         closure=[lib])
        self._check_node(lib, "lib/0.1@user/testing#123", deps=[], build_deps=[tool],
                         dependents=[app], closure=[tool])
        self._check_node(tool, "tool/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[lib], closure=[])

    def test_transitive_build_require_recipe_profile(self):
        # app -> lib -(br)-> gtest -(br)-> mingw
        # profile \---(br)-> mingw
        # app -(br)-> mingw
        mingw_ref = ConanFileReference.loads("mingw/0.1@user/testing")
        gtest_ref = ConanFileReference.loads("gtest/0.1@user/testing")
        lib_ref = ConanFileReference.loads("lib/0.1@user/testing")

        self._cache_recipe(mingw_ref, GenConanfile().with_name("mingw").with_version("0.1"))
        self._cache_recipe(gtest_ref, GenConanfile().with_name("gtest").with_version("0.1"))
        self._cache_recipe(lib_ref, GenConanfile().with_name("lib").with_version("0.1")
                                                  .with_build_requires(gtest_ref))
        profile_build_requires = {"*": [mingw_ref]}
        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(lib_ref),
                                      profile_build_requires=profile_build_requires)

        self.assertEqual(6, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        gtest = lib.dependencies[0].dst
        mingw_gtest = gtest.dependencies[0].dst
        mingw_lib = lib.dependencies[1].dst
        mingw_app = app.dependencies[1].dst

        self._check_node(app, "app/0.1@", deps=[lib], build_deps=[mingw_app], dependents=[],
                         closure=[mingw_app, lib])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[], build_deps=[mingw_lib, gtest],
                         dependents=[app], closure=[mingw_lib, gtest])
        self._check_node(gtest, "gtest/0.1@user/testing#123", deps=[], build_deps=[mingw_gtest],
                         dependents=[lib], closure=[mingw_gtest])
        # MinGW leaf nodes
        self._check_node(mingw_gtest, "mingw/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[gtest], closure=[])
        self._check_node(mingw_lib, "mingw/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[lib], closure=[])
        self._check_node(mingw_app, "mingw/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[app], closure=[])

    def test_not_conflict_transitive_build_requires(self):
        # Same as above, but gtest->(build_require)->zlib2
        zlib_ref = ConanFileReference.loads("zlib/0.1@user/testing")
        zlib_ref2 = ConanFileReference.loads("zlib/0.2@user/testing")
        gtest_ref = ConanFileReference.loads("gtest/0.1@user/testing")
        lib_ref = ConanFileReference.loads("lib/0.1@user/testing")

        self._cache_recipe(zlib_ref, GenConanfile().with_name("zlib").with_version("0.1"))
        self._cache_recipe(zlib_ref2, GenConanfile().with_name("zlib").with_version("0.2"))

        self._cache_recipe(gtest_ref, GenConanfile().with_name("gtest").with_version("0.1")
                                                    .with_build_requires(zlib_ref2))
        self._cache_recipe(lib_ref, GenConanfile().with_name("lib").with_version("0.1")
                                                  .with_require(zlib_ref)
                                                  .with_build_requires(gtest_ref))

        graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                               .with_require(lib_ref))

        self.assertEqual(5, len(graph.nodes))
        app = graph.root
        lib = app.dependencies[0].dst
        zlib = lib.dependencies[0].dst
        gtest = lib.dependencies[1].dst
        zlib2 = gtest.dependencies[0].dst
        self._check_node(app, "app/0.1@", deps=[lib], build_deps=[], dependents=[],
                         closure=[lib, zlib])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[zlib], build_deps=[gtest],
                         dependents=[app], closure=[gtest, zlib])

        self._check_node(gtest, "gtest/0.1@user/testing#123", deps=[], build_deps=[zlib2],
                         dependents=[lib], closure=[zlib2])

    def test_build_require_private(self):
        # app -> lib -(br)-> tool -(private)-> zlib
        zlib_ref = ConanFileReference.loads("zlib/0.1@user/testing")
        tool_ref = ConanFileReference.loads("tool/0.1@user/testing")
        lib_ref = ConanFileReference.loads("lib/0.1@user/testing")

        self._cache_recipe(zlib_ref, GenConanfile().with_name("zlib").with_version("0.1"))
        self._cache_recipe(tool_ref, GenConanfile().with_name("tool").with_version("0.1")
                                                   .with_require(zlib_ref, private=True))
        self._cache_recipe(lib_ref, GenConanfile().with_name("lib").with_version("0.1")
                                                  .with_build_requires(tool_ref))
        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(lib_ref))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        tool = lib.dependencies[0].dst
        zlib = tool.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], build_deps=[], dependents=[],
                         closure=[lib])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[], build_deps=[tool],
                         dependents=[app], closure=[tool])

        self._check_node(tool, "tool/0.1@user/testing#123", deps=[zlib], build_deps=[],
                         dependents=[lib], closure=[zlib])

        self._check_node(zlib, "zlib/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[tool], closure=[])
