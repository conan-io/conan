import pytest
from parameterized import parameterized

from conans.client.graph.graph import GraphError
from conans.model.ref import ConanFileReference
from conans.test.integration.graph.core.wip.graph_manager_base import GraphManagerTest
from conans.test.utils.tools import GenConanfile


def _check_transitive(node, transitive_deps):
    # TODO: repeated code
    values = list(node.transitive_deps.values())
    print(values)
    print(transitive_deps)
    assert len(values) == len(transitive_deps)

    for v1, v2 in zip(values, transitive_deps):
        assert v1.node is v2[0]
        assert v1.require.include is v2[1]
        assert v1.require.link is v2[2]
        assert v1.require.build is v2[3]
        assert v1.require.run is v2[4]


class BuildRequiresGraphTest(GraphManagerTest):

    @parameterized.expand([("recipe", ), ("profile", )])
    def test_basic(self, build_require):
        # app -(br)-> cmake
        self._cache_recipe("cmake/0.1", GenConanfile())
        if build_require == "recipe":
            profile_build_requires = None
            conanfile = GenConanfile("app", "0.1").with_build_requires("cmake/0.1")
        else:
            profile_build_requires = {"*": [ConanFileReference.loads("cmake/0.1")]}
            conanfile = GenConanfile("app", "0.1")

        deps_graph = self.build_graph(conanfile, profile_build_requires=profile_build_requires,
                                      install=False)

        # Build requires always apply to the consumer
        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        cmake = app.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[cmake], dependents=[])
        self._check_node(cmake, "cmake/0.1#123", deps=[], dependents=[app])

    def test_lib_build_require(self):
        # app -> lib -(br)-> cmake
        self._cache_recipe("cmake/0.1", GenConanfile())
        self._cache_recipe("lib/0.1", GenConanfile().with_build_requires("cmake/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_require("lib/0.1"))

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        cmake = lib.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[cmake], dependents=[app])
        self._check_node(cmake, "cmake/0.1#123", deps=[], dependents=[lib])

        # node, include, link, build, run
        _check_transitive(app, [(lib, True, True, False, None)])  # TODO: Check run=None
        _check_transitive(lib, [(cmake, False, False, True, True)])

    def test_build_require_transitive(self):
        # app -> lib -(br)-> cmake -> zlib (static)
        self._cache_recipe("zlib/0.1", GenConanfile("zlib", "0.1").with_shared_option(False))
        self._cache_recipe("cmake/0.1", GenConanfile().with_require("zlib/0.1"))
        self._cache_recipe("lib/0.1", GenConanfile().with_build_requires("cmake/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_require("lib/0.1"))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        cmake = lib.dependencies[0].dst
        zlib = cmake.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[cmake], dependents=[app])
        self._check_node(cmake, "cmake/0.1#123", deps=[zlib], dependents=[lib])
        self._check_node(zlib, "zlib/0.1#123", deps=[], dependents=[cmake])

        # node, include, link, build, run
        _check_transitive(app, [(lib, True, True, False, None)])  # TODO: Check run=None
        _check_transitive(lib, [(cmake, False, False, True, True)])

    def test_build_require_transitive_shared(self):
        # app -> lib -(br)-> cmake -> zlib (shared)
        self._cache_recipe("zlib/0.1", GenConanfile("zlib", "0.1").with_shared_option(True))
        self._cache_recipe("cmake/0.1", GenConanfile().with_require("zlib/0.1"))
        self._cache_recipe("lib/0.1", GenConanfile().with_build_requires("cmake/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_require("lib/0.1"))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        cmake = lib.dependencies[0].dst
        zlib = cmake.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[cmake], dependents=[app])
        self._check_node(cmake, "cmake/0.1#123", deps=[zlib], dependents=[lib])
        self._check_node(zlib, "zlib/0.1#123", deps=[], dependents=[cmake])

        # node, include, link, build, run
        _check_transitive(app, [(lib, True, True, False, None)])  # TODO: Check run=None
        _check_transitive(lib, [(cmake, False, False, True, True),
                                (zlib, False, False, True, True)])




    @pytest.mark.xfail(reason="Not updated yet")
    def test_transitive_build_require_recipe_profile(self):
        # app -> lib -(br)-> gtest
        # profile \---(br)-> mingw
        # app -(br)-> mingw
        mingw_ref = ConanFileReference.loads("mingw/0.1@user/testing")
        gtest_ref = ConanFileReference.loads("gtest/0.1@user/testing")
        lib_ref = ConanFileReference.loads("lib/0.1@user/testing")

        self._cache_recipe(mingw_ref, GenConanfile().with_name("mingw").with_version("0.1"))
        self._cache_recipe(gtest_ref, GenConanfile().with_name("gtest").with_version("0.1"))
        self._cache_recipe(lib_ref, GenConanfile()
                                                  .with_build_requires(gtest_ref))
        profile_build_requires = {"*": [mingw_ref]}
        deps_graph = self.build_graph(GenConanfile("app", "0.1")
                                                    .with_require(lib_ref),
                                      profile_build_requires=profile_build_requires)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        gtest = lib.dependencies[0].dst

        mingw_lib = lib.dependencies[1].dst
        mingw_app = app.dependencies[1].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[], dependents=[app])
        self._check_node(gtest, "gtest/0.1@user/testing#123", deps=[], dependents=[lib])
        # MinGW leaf nodes
        self._check_node(mingw_lib, "mingw/0.1@user/testing#123", deps=[], dependents=[lib])
        self._check_node(mingw_app, "mingw/0.1@user/testing#123", deps=[], dependents=[app])

    @pytest.mark.xfail(reason="Not updated yet")
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
        self._cache_recipe(lib_ref, GenConanfile()
                                                  .with_require(zlib_ref)
                                                  .with_build_requires(gtest_ref))

        graph = self.build_graph(GenConanfile("app", "0.1")
                                               .with_require(lib_ref))

        self.assertEqual(5, len(graph.nodes))
        app = graph.root
        lib = app.dependencies[0].dst
        zlib = lib.dependencies[0].dst
        gtest = lib.dependencies[1].dst
        zlib2 = gtest.dependencies[0].dst
        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[zlib], dependents=[app])

        self._check_node(gtest, "gtest/0.1@user/testing#123", deps=[], dependents=[lib])

    @pytest.mark.xfail(reason="Not updated yet")
    def test_build_require_private(self):
        # app -> lib -(br)-> cmake -(private)-> zlib
        zlib_ref = ConanFileReference.loads("zlib/0.1@user/testing")
        cmake_ref = ConanFileReference.loads("cmake/0.1@user/testing")
        lib_ref = ConanFileReference.loads("lib/0.1@user/testing")

        self._cache_recipe(zlib_ref, GenConanfile().with_name("zlib").with_version("0.1"))
        self._cache_recipe(cmake_ref, GenConanfile()
                                                   .with_require(zlib_ref, private=True))
        self._cache_recipe(lib_ref, GenConanfile()
                                                  .with_build_requires(cmake_ref))
        deps_graph = self.build_graph(GenConanfile("app", "0.1")
                                                    .with_require(lib_ref))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        cmake = lib.dependencies[0].dst
        zlib = cmake.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[], dependents=[app])

        self._check_node(cmake, "cmake/0.1@user/testing#123", deps=[zlib], dependents=[lib])

        self._check_node(zlib, "zlib/0.1@user/testing#123", deps=[], dependents=[cmake])


class TestBuildRequiresTransitivityDiamond(GraphManagerTest):

    def test_build_require_transitive_static(self):
        # app -> lib -(br)-> cmake -> zlib1 (static)
        #          \--(br)-> mingw -> zlib2 (static)
        self._cache_recipe("zlib/0.1", GenConanfile().with_shared_option(False))
        self._cache_recipe("zlib/0.2", GenConanfile().with_shared_option(False))
        self._cache_recipe("cmake/0.1", GenConanfile().with_require("zlib/0.1"))
        self._cache_recipe("mingw/0.1", GenConanfile().with_require("zlib/0.2"))
        self._cache_recipe("lib/0.1", GenConanfile().with_build_requires("cmake/0.1", "mingw/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_require("lib/0.1"))

        self.assertEqual(6, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        cmake = lib.dependencies[0].dst
        mingw = lib.dependencies[1].dst
        zlib1 = cmake.dependencies[0].dst
        zlib2 = mingw.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[cmake, mingw], dependents=[app])
        self._check_node(cmake, "cmake/0.1#123", deps=[zlib1], dependents=[lib])
        self._check_node(zlib1, "zlib/0.1#123", deps=[], dependents=[cmake])
        self._check_node(mingw, "mingw/0.1#123", deps=[zlib2], dependents=[lib])
        self._check_node(zlib2, "zlib/0.2#123", deps=[], dependents=[mingw])

        # node, include, link, build, run
        _check_transitive(app, [(lib, True, True, False, None)])
        _check_transitive(lib, [(cmake, False, False, True, True),
                                (mingw, False, False, True, True)])

    def test_build_require_transitive_shared(self):
        # app -> lib -(br)-> cmake -> zlib1 (shared)
        #          \--(br)-> mingw -> zlib2 (shared) -> SHOULD CONFLICT
        self._cache_recipe("zlib/0.1", GenConanfile().with_shared_option(True))
        self._cache_recipe("zlib/0.2", GenConanfile().with_shared_option(True))
        self._cache_recipe("cmake/0.1", GenConanfile().with_require("zlib/0.1"))
        self._cache_recipe("mingw/0.1", GenConanfile().with_require("zlib/0.2"))
        self._cache_recipe("lib/0.1", GenConanfile().with_build_requires("cmake/0.1", "mingw/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_require("lib/0.1"),
                                      install=False)

        self.assertEqual(6, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        cmake = lib.dependencies[0].dst
        mingw = lib.dependencies[1].dst
        zlib1 = cmake.dependencies[0].dst
        zlib2 = mingw.dependencies[0].dst

        assert zlib1 is not zlib2

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[cmake, mingw], dependents=[app])
        self._check_node(cmake, "cmake/0.1#123", deps=[zlib1], dependents=[lib])
        self._check_node(zlib1, "zlib/0.1#123", deps=[], dependents=[cmake])
        self._check_node(mingw, "mingw/0.1#123", deps=[zlib2], dependents=[lib])
        self._check_node(zlib2, "zlib/0.2#123", deps=[], dependents=[mingw])

        assert lib.conflict == (GraphError.VERSION_CONFLICT, [zlib1, zlib2])

    @pytest.mark.xfail(reason="Not updated yet")
    def test_build_require_conflict(self):
        # https://github.com/conan-io/conan/issues/4931
        # cheetah -> gazelle -> grass/0.1
        #    \--(br)----------> grass/0.2
        grass01_ref = ConanFileReference.loads("grass/0.1@user/testing")
        grass02_ref = ConanFileReference.loads("grass/0.2@user/testing")
        gazelle_ref = ConanFileReference.loads("gazelle/0.1@user/testing")

        self._cache_recipe(grass01_ref, GenConanfile().with_name("grass").with_version("0.1"))
        self._cache_recipe(grass02_ref, GenConanfile().with_name("grass").with_version("0.2"))
        self._cache_recipe(gazelle_ref, GenConanfile().with_name("gazelle").with_version("0.1")
                                                      .with_require(grass01_ref))

        deps_graph = self.build_graph(GenConanfile().with_name("cheetah").with_version("0.1")
                                           .with_require(gazelle_ref)
                                           .with_build_requires(grass02_ref))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba1 = libb.dependencies[0].dst
        liba2 = libc.dependencies[0].dst
        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba1], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba2], dependents=[app])

        self._check_node(liba1, "liba/0.1#123", dependents=[libb])
        # TODO: Conflicted without revision
        self._check_node(liba2, "liba/0.2", dependents=[libc])

        assert liba1.conflict == liba2
        assert liba2.conflict == liba1

    @pytest.mark.xfail(reason="Not updated yet")
    def test_build_require_link_order(self):
        # https://github.com/conan-io/conan/issues/4931
        # cheetah -> gazelle -> grass
        #    \--(br)------------/
        grass01_ref = ConanFileReference.loads("grass/0.1@user/testing")
        gazelle_ref = ConanFileReference.loads("gazelle/0.1@user/testing")

        self._cache_recipe(grass01_ref, GenConanfile().with_name("grass").with_version("0.1"))
        self._cache_recipe(gazelle_ref, GenConanfile().with_name("gazelle").with_version("0.1")
                                                      .with_require(grass01_ref))

        deps_graph = self.build_graph(GenConanfile().with_name("cheetah").with_version("0.1")
                                                    .with_require(gazelle_ref)
                                                    .with_build_requires(grass01_ref))

        self.assertEqual(3, len(deps_graph.nodes))
        cheetah = deps_graph.root
        gazelle = cheetah.dependencies[0].dst
        grass = gazelle.dependencies[0].dst
        grass2 = cheetah.dependencies[1].dst

        self._check_node(cheetah, "cheetah/0.1@", deps=[gazelle], dependents=[])
        self.assertListEqual(list(cheetah.conanfile.deps_cpp_info.libs),
                             ['mylibgazelle0.1lib', 'mylibgrass0.1lib'])
