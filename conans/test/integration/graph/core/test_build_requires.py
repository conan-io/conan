import textwrap

import pytest

from parameterized import parameterized

from conans.client.graph.graph_error import GraphError
from conans.model.recipe_ref import RecipeReference
from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest
from conans.test.utils.tools import GenConanfile, NO_SETTINGS_PACKAGE_ID, TestClient


def _check_transitive(node, transitive_deps):
    values = list(node.transitive_deps.values())

    assert len(values) == len(transitive_deps), f"{node}:{len(values)} != {len(transitive_deps)}"

    for v1, v2 in zip(values, transitive_deps):
        # asserts were difficult to debug
        if v1.node is not v2[0]: raise Exception(f"{v1.node}!={v2[0]}")
        if v1.require.headers is not v2[1]: raise Exception(f"{v1.node}!={v2[0]} headers")
        if v1.require.libs is not v2[2]: raise Exception(f"{v1.node}!={v2[0]} libs")
        if v1.require.build is not v2[3]: raise Exception(f"{v1.node}!={v2[0]} build")
        if v1.require.run is not v2[4]: raise Exception(f"{v1.node}!={v2[0]} run")
        if len(v2) >= 6:
            if v1.require.test is not v2[5]: raise Exception(f"{v1.node}!={v2[0]} test")


class BuildRequiresGraphTest(GraphManagerTest):

    @parameterized.expand([("recipe", ), ("profile", )])
    def test_basic(self, build_require):
        # app -(br)-> cmake
        self._cache_recipe("cmake/0.1", GenConanfile())
        if build_require == "recipe":
            profile_build_requires = None
            conanfile = GenConanfile("app", "0.1").with_tool_requires("cmake/0.1")
        else:
            profile_build_requires = {"*": [RecipeReference.loads("cmake/0.1")]}
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
        self._cache_recipe("lib/0.1", GenConanfile().with_tool_requires("cmake/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_require("lib/0.1"))

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        cmake = lib.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[cmake], dependents=[app])
        self._check_node(cmake, "cmake/0.1#123", deps=[], dependents=[lib])

        # node, include, link, build, run
        _check_transitive(app, [(lib, True, True, False, False)])
        _check_transitive(lib, [(cmake, False, False, True, True)])

    @parameterized.expand([("shared", ), ("static", ), ("notrun", ), ("run", )])
    def test_build_require_transitive(self, cmakelib_type):
        # app -> lib -(br)-> cmake -> cmakelib (cmakelib_type)

        if cmakelib_type in ("notrun", "run"):  # Unknown
            cmakelib = GenConanfile().with_settings("os")
        else:
            cmakelib = GenConanfile().with_settings("os").\
                with_shared_option(cmakelib_type == "shared")
        run = True if cmakelib_type == "run" else None  # Not necessary to specify

        self._cache_recipe("cmakelib/0.1", cmakelib)
        self._cache_recipe("cmake/0.1", GenConanfile().with_settings("os").
                           with_requirement("cmakelib/0.1", run=run))
        self._cache_recipe("lib/0.1", GenConanfile().with_settings("os").
                           with_tool_requires("cmake/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_settings("os").
                                      with_require("lib/0.1"))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        cmake = lib.dependencies[0].dst
        cmakelib = cmake.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[], settings={"os": "Linux"})
        self._check_node(lib, "lib/0.1#123", deps=[cmake], dependents=[app],
                         settings={"os": "Linux"})
        self._check_node(cmake, "cmake/0.1#123", deps=[cmakelib], dependents=[lib],
                         settings={"os": "Windows"})
        self._check_node(cmakelib, "cmakelib/0.1#123", deps=[], dependents=[cmake],
                         settings={"os": "Windows"})

        # node, include, link, build, run
        _check_transitive(app, [(lib, True, True, False, False)])

        if cmakelib_type in ("static", "notrun"):
            _check_transitive(lib, [(cmake, False, False, True, True)])
        else:
            _check_transitive(lib, [(cmake, False, False, True, True),
                                    (cmakelib, False, False, True, True)])

    def test_build_require_bootstrap(self):
        # app -> lib -(br)-> cmake/2 -(br)-> cmake/1
        self._cache_recipe("cmake/0.1", GenConanfile())
        self._cache_recipe("cmake/0.2", GenConanfile().with_tool_requires("cmake/0.1"))
        self._cache_recipe("lib/0.1", GenConanfile().with_tool_requires("cmake/0.2"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_require("lib/0.1"))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        cmake2 = lib.dependencies[0].dst
        cmake1 = cmake2.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[cmake2], dependents=[app])
        self._check_node(cmake2, "cmake/0.2#123", deps=[cmake1], dependents=[lib])
        self._check_node(cmake1, "cmake/0.1#123", deps=[], dependents=[cmake2])

        # node, include, link, build, run
        _check_transitive(app, [(lib, True, True, False, False)])
        _check_transitive(lib, [(cmake2, False, False, True, True)])
        _check_transitive(cmake2, [(cmake1, False, False, True, True)])

    def test_build_require_private(self):
        # app -> lib -(br)-> cmake -(private)-> zlib
        self._cache_recipe("zlib/0.1", GenConanfile())
        self._cache_recipe("cmake/0.1", GenConanfile().with_requirement("zlib/0.1", visible=False))
        self._cache_recipe("lib/0.1", GenConanfile().with_tool_requires("cmake/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_require("lib/0.1"))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        cmake = lib.dependencies[0].dst
        zlib = cmake.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[cmake], dependents=[app])
        self._check_node(cmake, "cmake/0.1#123", deps=[zlib], dependents=[lib])
        self._check_node(zlib, "zlib/0.1#123", deps=[], dependents=[cmake])

        # node, include, link, build, run
        _check_transitive(app, [(lib, True, True, False, False)])
        _check_transitive(lib, [(cmake, False, False, True, True)])
        _check_transitive(cmake, [(zlib, True, True, False, False)])


class TestBuildRequiresTransitivityDiamond(GraphManagerTest):

    def test_build_require_transitive_static(self):
        # app -> lib -(br)-> cmake -> zlib1 (static)
        #          \--(br)-> mingw -> zlib2 (static)
        self._cache_recipe("zlib/0.1", GenConanfile().with_shared_option(False))
        self._cache_recipe("zlib/0.2", GenConanfile().with_shared_option(False))
        self._cache_recipe("cmake/0.1", GenConanfile().with_require("zlib/0.1"))
        self._cache_recipe("mingw/0.1", GenConanfile().with_require("zlib/0.2"))
        self._cache_recipe("lib/0.1", GenConanfile().with_tool_requires("cmake/0.1",
                                                                              "mingw/0.1"))
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
        _check_transitive(app, [(lib, True, True, False, False)])
        _check_transitive(lib, [(cmake, False, False, True, True),
                                (mingw, False, False, True, True)])

    def test_build_require_transitive_shared(self):
        # app -> lib -(br)-> cmake -> zlib1 (shared)
        #          \--(br)-> mingw -> zlib2 (shared) -> SHOULD CONFLICT
        self._cache_recipe("zlib/0.1", GenConanfile().with_shared_option(True))
        self._cache_recipe("zlib/0.2", GenConanfile().with_shared_option(True))
        self._cache_recipe("cmake/0.1", GenConanfile().with_require("zlib/0.1"))
        self._cache_recipe("mingw/0.1", GenConanfile().with_require("zlib/0.2"))
        self._cache_recipe("lib/0.1", GenConanfile().with_tool_requires("cmake/0.1",
                                                                              "mingw/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_require("lib/0.1"),
                                      install=False)

        assert deps_graph.error.kind == GraphError.RUNTIME

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

    @pytest.mark.xfail(reason="Not updated yet")
    def test_build_require_conflict(self):
        # https://github.com/conan-io/conan/issues/4931
        # cheetah -> gazelle -> grass/0.1
        #    \--(br)----------> grass/0.2
        grass01_ref = RecipeReference.loads("grass/0.1@user/testing")
        grass02_ref = RecipeReference.loads("grass/0.2@user/testing")
        gazelle_ref = RecipeReference.loads("gazelle/0.1@user/testing")

        self._cache_recipe(grass01_ref, GenConanfile().with_name("grass").with_version("0.1"))
        self._cache_recipe(grass02_ref, GenConanfile().with_name("grass").with_version("0.2"))
        self._cache_recipe(gazelle_ref, GenConanfile().with_name("gazelle").with_version("0.1")
                                                      .with_require(grass01_ref))

        deps_graph = self.build_graph(GenConanfile().with_name("cheetah").with_version("0.1")
                                           .with_require(gazelle_ref)
                                           .with_tool_requires(grass02_ref))

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
        grass01_ref = RecipeReference.loads("grass/0.1@user/testing")
        gazelle_ref = RecipeReference.loads("gazelle/0.1@user/testing")

        self._cache_recipe(grass01_ref, GenConanfile().with_name("grass").with_version("0.1"))
        self._cache_recipe(gazelle_ref, GenConanfile().with_name("gazelle").with_version("0.1")
                                                      .with_require(grass01_ref))

        deps_graph = self.build_graph(GenConanfile().with_name("cheetah").with_version("0.1")
                                                    .with_require(gazelle_ref)
                                                    .with_tool_requires(grass01_ref))

        self.assertEqual(3, len(deps_graph.nodes))
        cheetah = deps_graph.root
        gazelle = cheetah.dependencies[0].dst
        grass = gazelle.dependencies[0].dst
        grass2 = cheetah.dependencies[1].dst

        self._check_node(cheetah, "cheetah/0.1@", deps=[gazelle], dependents=[])
        self.assertListEqual(list(cheetah.conanfile.deps_cpp_info.libs),
                             ['mylibgazelle0.1lib', 'mylibgrass0.1lib'])


class TestTestRequire(GraphManagerTest):

    def test_basic(self):
        # app -(tr)-> gtest
        self._cache_recipe("gtest/0.1", GenConanfile())
        conanfile = GenConanfile("app", "0.1").with_test_requires("gtest/0.1")

        deps_graph = self.build_graph(conanfile)

        # Build requires always apply to the consumer
        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        gtest = app.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[gtest], dependents=[])
        self._check_node(gtest, "gtest/0.1#123", deps=[], dependents=[app])

        # node, include, link, build, run, test
        _check_transitive(app, [(gtest, True, True, False, False, True)])

    def test_lib_build_require(self):
        # app -> lib -(tr)-> gtest
        self._cache_recipe("gtest/0.1", GenConanfile())
        self._cache_recipe("lib/0.1", GenConanfile().with_test_requires("gtest/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_require("lib/0.1"))

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        gtest = lib.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[gtest], dependents=[app])
        self._check_node(gtest, "gtest/0.1#123", deps=[], dependents=[lib])

        # node, include, link, build, run
        _check_transitive(app, [(lib, True, True, False, False)])
        _check_transitive(lib, [(gtest, True, True, False, False)])

    def test_lib_build_require_transitive(self):
        # app -> lib -(tr)-> gtest
        self._cache_recipe("gtest/0.1", GenConanfile())
        self._cache_recipe("lib/0.1", GenConanfile().with_test_requires("gtest/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_require("lib/0.1"))

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        gtest = lib.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[gtest], dependents=[app])
        self._check_node(gtest, "gtest/0.1#123", deps=[], dependents=[lib])

        # node, include, link, build, run
        _check_transitive(app, [(lib, True, True, False, False)])
        _check_transitive(lib, [(gtest, True, True, False, False)])

    @parameterized.expand([("shared",), ("static",), ("notrun",), ("run",)])
    def test_test_require_transitive(self, gtestlib_type):
        # app -> lib -(tr)-> gtest -> gtestlib (gtestlib_type)

        if gtestlib_type in ("notrun", "run"):  # Unknown
            gtestlib = GenConanfile().with_settings("os")
        else:
            gtestlib = GenConanfile().with_settings("os"). \
                with_shared_option(gtestlib_type == "shared")
        run = True if gtestlib_type == "run" else None  # Not necessary to specify

        self._cache_recipe("gtestlib/0.1", gtestlib)
        self._cache_recipe("gtest/0.1", GenConanfile().with_settings("os").
                           with_requirement("gtestlib/0.1", run=run))
        self._cache_recipe("lib/0.1", GenConanfile().with_settings("os").
                           with_test_requires("gtest/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_settings("os").
                                      with_require("lib/0.1"))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        gtest = lib.dependencies[0].dst
        gtestlib = gtest.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[], settings={"os": "Linux"})
        self._check_node(lib, "lib/0.1#123", deps=[gtest], dependents=[app],
                         settings={"os": "Linux"})
        self._check_node(gtest, "gtest/0.1#123", deps=[gtestlib], dependents=[lib],
                         settings={"os": "Linux"})
        self._check_node(gtestlib, "gtestlib/0.1#123", deps=[], dependents=[gtest],
                         settings={"os": "Linux"})

        # node, include, link, build, run
        _check_transitive(app, [(lib, True, True, False, False)])  # TODO: Check run=None

        if gtestlib_type in ("shared", "run"):
            _check_transitive(lib, [(gtest, True, True, False, False),
                                    (gtestlib, True, True, False, True)])
        elif gtestlib_type == "static":
            _check_transitive(lib, [(gtest, True, True, False, False),
                                    (gtestlib, True, True, False, False)])
        elif gtestlib_type == "notrun":
            _check_transitive(lib, [(gtest, True, True, False, False),
                                    (gtestlib, True, True, False, False)])

    def test_trait_aggregated(self):
        # app -> lib -(tr)-> gtest -> zlib
        #         \-------------------/
        # If zlib is in the host context, a dependency for host, better test=False trait
        self._cache_recipe("zlib/0.1", GenConanfile())
        self._cache_recipe("gtest/0.1", GenConanfile().with_requires("zlib/0.1"))
        self._cache_recipe("lib/0.1", GenConanfile().with_test_requires("gtest/0.1")
                                                    .with_requires("zlib/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_require("lib/0.1"))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        gtest = lib.dependencies[1].dst
        zlib = gtest.dependencies[0].dst
        zlib2 = lib.dependencies[0].dst
        assert zlib is zlib2

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[zlib, gtest], dependents=[app])
        self._check_node(gtest, "gtest/0.1#123", deps=[zlib], dependents=[lib])
        self._check_node(zlib, "zlib/0.1#123", deps=[], dependents=[gtest, lib])

        # node, include, link, build, run
        _check_transitive(app, [(lib, True, True, False, False),
                                (zlib, True, True, False, False, False)])
        _check_transitive(lib, [(gtest, True, True, False, False),
                                (zlib, True, True, False, False, False)])


class BuildRequiresPackageIDTest(GraphManagerTest):

    def test_default_no_affect(self,):
        # app -> lib -(br)-> cmake
        self.recipe_conanfile("cmake/0.1", GenConanfile())
        self.recipe_conanfile("lib/0.1", GenConanfile().with_tool_requires("cmake/0.1"))

        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_requires("lib/0.1"))

        # Build requires always apply to the consumer
        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        cmake = lib.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[cmake], dependents=[app])
        assert lib.package_id == NO_SETTINGS_PACKAGE_ID
        self._check_node(cmake, "cmake/0.1#123", deps=[], dependents=[lib])

    def test_minor_mode(self,):
        # app -> lib -(br)-> cmake
        self.recipe_conanfile("cmake/0.1", GenConanfile())
        self.recipe_conanfile("lib/0.1", GenConanfile().
                              with_tool_requirement("cmake/[*]", package_id_mode="minor_mode"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_requires("lib/0.1"))

        # Build requires always apply to the consumer
        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        cmake = lib.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[cmake], dependents=[app])
        assert lib.package_id == "6b92478cba14dbdc06d4e991430d3c1c04959d4a"
        assert lib.package_id != NO_SETTINGS_PACKAGE_ID
        self._check_node(cmake, "cmake/0.1#123", deps=[], dependents=[lib])

        # Change the dependency to next minor
        self.recipe_conanfile("cmake/0.2", GenConanfile())
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_requires("lib/0.1"))

        # Build requires always apply to the consumer
        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        assert lib.package_id == "2813db72897dd13aca2af071efe8ecb116f679ed"
        assert lib.package_id != NO_SETTINGS_PACKAGE_ID


class PublicBuildRequiresTest(GraphManagerTest):

    def test_simple(self):
        # app -> lib -(br public)-> cmake
        self.recipe_conanfile("cmake/0.1", GenConanfile())
        self.recipe_conanfile("lib/0.1", GenConanfile()
                              .with_tool_requirement("cmake/0.1", visible=True))

        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_requires("lib/0.1"))

        # Build requires always apply to the consumer
        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        cmake = lib.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[cmake], dependents=[app])
        self._check_node(cmake, "cmake/0.1#123", deps=[], dependents=[lib])

        # node, include, link, build, run
        _check_transitive(lib, [(cmake, False, False, True, True)])
        _check_transitive(app, [(lib, True, True, False, False),
                                (cmake, False, False, True, False)])

    def test_conflict_diamond(self):
        # app -> libb -(br public)-> cmake/0.1
        #   \--> libc -(br public)-> cmake/0.2
        self.recipe_conanfile("cmake/0.1", GenConanfile())
        self.recipe_conanfile("cmake/0.2", GenConanfile())
        self.recipe_conanfile("libb/0.1",
                              GenConanfile().with_tool_requirement("cmake/0.1", visible=True))
        self.recipe_conanfile("libc/0.1",
                              GenConanfile().with_tool_requirement("cmake/0.2", visible=True))

        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_requires("libb/0.1",
                                                                               "libc/0.1"),
                                      install=False)

        assert deps_graph.error.kind == GraphError.VERSION_CONFLICT

        # Build requires always apply to the consumer
        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        cmake1 = libb.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[libb, libc], dependents=[])
        self._check_node(libb, "libb/0.1#123", deps=[cmake1], dependents=[app])
        self._check_node(cmake1, "cmake/0.1#123", deps=[], dependents=[libb])

    def test_tool_requires(self):
        # app -> libb -(br public)-> protobuf/0.1
        #           \--------------> protobuf/0.2
        self.recipe_conanfile("protobuf/0.1", GenConanfile())
        self.recipe_conanfile("protobuf/0.2", GenConanfile())
        self.recipe_conanfile("libb/0.1",
                              GenConanfile().with_tool_requirement("protobuf/0.1", visible=True)
                              .with_require("protobuf/0.2"))

        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_requires("libb/0.1"))

        # Build requires always apply to the consumer
        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        protobuf_host = libb.dependencies[0].dst
        protobuf_build = libb.dependencies[1].dst

        self._check_node(app, "app/0.1@", deps=[libb], dependents=[])
        self._check_node(libb, "libb/0.1#123", deps=[protobuf_host, protobuf_build],
                         dependents=[app])
        self._check_node(protobuf_host, "protobuf/0.2#123", deps=[], dependents=[libb])
        self._check_node(protobuf_build, "protobuf/0.1#123", deps=[], dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (protobuf_host, True, True, False, False),
                                (protobuf_build, False, False, True, False)])

    def test_tool_requires_override(self):
        # app -> libb -(br public)-> protobuf/0.1
        #           \--------------> protobuf/0.2
        #  \---(br, override)------> protobuf/0.2
        self.recipe_conanfile("protobuf/0.1", GenConanfile())
        self.recipe_conanfile("protobuf/0.2", GenConanfile())
        self.recipe_conanfile("libb/0.1",
                              GenConanfile().with_tool_requirement("protobuf/0.1", visible=True)
                              .with_require("protobuf/0.2"))

        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_requires("libb/0.1")
                                      .with_tool_requirement("protobuf/0.2", override=True))

        # Build requires always apply to the consumer
        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        protobuf_host = libb.dependencies[0].dst
        protobuf_build = libb.dependencies[1].dst

        self._check_node(app, "app/0.1@", deps=[libb], dependents=[])
        self._check_node(libb, "libb/0.1#123", deps=[protobuf_host, protobuf_build],
                         dependents=[app])
        self._check_node(protobuf_host, "protobuf/0.2#123", deps=[], dependents=[libb])
        self._check_node(protobuf_build, "protobuf/0.2#123", deps=[], dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (protobuf_host, True, True, False, False),
                                (protobuf_build, False, False, True, False)])
        _check_transitive(libb, [(protobuf_host, True, True, False, False),
                                 (protobuf_build, False, False, True, True)])

    def test_test_require(self):
        # app -(tr)-> gtest/0.1
        # This test should survive in 2.0
        tool_ref = RecipeReference.loads("gtest/0.1")
        self._cache_recipe(tool_ref, GenConanfile("gtest", "0.1"))

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "app"
                version = "0.1"
                def build_requirements(self):
                    self.test_requires("gtest/0.1")
            """)
        deps_graph = self.build_graph(conanfile)

        # Build requires always apply to the consumer
        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        tool = app.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[tool], dependents=[])
        self._check_node(tool, "gtest/0.1#123", deps=[], dependents=[app])


class TestLoops(GraphManagerTest):

    def test_direct_loop_error(self):
        # app -(br)-> cmake/0.1 -(br itself)-> cmake/0.1....
        # causing an infinite loop
        self._cache_recipe("cmake/0.1", GenConanfile().with_tool_requires("cmake/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_build_requires("cmake/0.1"),
                                      install=False)

        assert deps_graph.error.kind == GraphError.LOOP

        # Build requires always apply to the consumer
        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        tool = app.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[tool], dependents=[])
        self._check_node(tool, "cmake/0.1#123", deps=[], dependents=[app])

    def test_indirect_loop_error(self):
        # app -(br)-> gtest/0.1 -(br)-> cmake/0.1 -(br)->gtest/0.1 ....
        # causing an infinite loop
        self._cache_recipe("gtest/0.1", GenConanfile().with_tool_requires("cmake/0.1"))
        self._cache_recipe("cmake/0.1", GenConanfile().with_test_requires("gtest/0.1"))

        deps_graph = self.build_graph(GenConanfile().with_build_requires("cmake/0.1"),
                                      install=False)

        assert deps_graph.error.kind == GraphError.LOOP

        # Build requires always apply to the consumer
        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        cmake = app.dependencies[0].dst
        gtest = cmake.dependencies[0].dst
        cmake2 = gtest.dependencies[0].dst

        assert deps_graph.error.ancestor == cmake
        assert deps_graph.error.node == cmake2


def test_tool_requires():
    """Testing temporary tool_requires attribute being "an alias" of build_require and
    introduced to provide a compatible recipe with 2.0. At 2.0, the meaning of a build require being
    a 'tool' will be a tool_require."""

    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=tool1 --version=1.0")
    client.run("create . --name=tool2 --version=1.0")
    client.run("create . --name=tool3 --version=1.0")
    client.run("create . --name=tool4 --version=1.0")

    consumer = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            tool_requires = "tool2/1.0"
            build_requires = "tool3/1.0"

            def build_requirements(self):
                self.tool_requires("tool1/1.0")
                self.build_requires("tool4/1.0")

            def generate(self):
                assert len(self.dependencies.build.values()) == 4
    """)
    client.save({"conanfile.py": consumer})
    client.run("create . --name=consumer --version=1.0")
    client.assert_listed_require({"tool1/1.0": "Cache",
                                  "tool2/1.0": "Cache",
                                  "tool3/1.0": "Cache",
                                  "tool4/1.0": "Cache"}, build=True)


class TestDuplicateBuildRequires:
    """ what happens when you require and tool_require the same dependency
    """
    # https://github.com/conan-io/conan/issues/11179

    @pytest.fixture()
    def client(self):
        client = TestClient()
        msg = "self.output.info('This is the binary for OS={}'.format(self.info.settings.os))"
        msg2 = "self.output.info('This is in context={}'.format(self.context))"
        client.save({"conanfile.py": GenConanfile().with_settings("os").with_package_id(msg)
                                                                       .with_package_id(msg2)})
        client.run("create . --name=tool1 --version=1.0 -s os=Windows")
        client.run("create . --name=tool2 --version=1.0 -s os=Windows")
        client.run("create . --name=tool3 --version=1.0 -s os=Windows")
        client.run("create . --name=tool4 --version=1.0 -s os=Windows")

        consumer = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "consumer"
                version = "1.0"
                tool_requires = "tool2/1.0"
                build_requires = "tool3/1.0"
                def requirements(self):
                    self.requires("tool4/1.0")
                def build_requirements(self):
                    self.build_requires("tool4/1.0")
                    self.tool_requires("tool1/1.0")
                def generate(self):
                    host_deps = sorted([d.ref for d, _ in self.dependencies.host.items()])
                    build_deps = sorted([d.ref for d, _ in self.dependencies.build.items()])
                    self.output.info("HOST DEPS: {}".format(host_deps))
                    self.output.info("BUILD DEPS: {}".format(build_deps))
                    assert len(host_deps) == 1, host_deps
                    assert len(build_deps) == 4, build_deps
            """)
        client.save({"conanfile.py": consumer})
        return client

    def test_tool_requires_in_test_package(self, client):
        """Test that tool requires can be listed as build and host requirements"""
        test = textwrap.dedent("""\
            from conan import ConanFile
            class Test(ConanFile):
                def build_requirements(self):
                    self.tool_requires(self.tested_reference_str)
                def test(self):
                    pass
        """)

        client.save({"test_package/conanfile.py": test})
        client.run("create . -s:b os=Windows -s:h os=Linux  --build-require")
        assert "This is the binary for OS=Linux" not in client.out
        assert "This is in context=host" not in client.out
        client.assert_listed_require({"consumer/1.0": "Cache"}, build=True)
        for tool in "tool1", "tool2", "tool3", "tool4":
            client.assert_listed_require({f"{tool}/1.0": "Cache"}, build=True)
            assert f"{tool}/1.0: This is the binary for OS=Windows" in client.out
            assert f"{tool}/1.0: This is in context=build" in client.out

        assert "consumer/1.0: HOST DEPS: [tool4/1.0]" in client.out
        assert "consumer/1.0: BUILD DEPS: [tool1/1.0, tool2/1.0, tool3/1.0, tool4/1.0]" in client.out

    def test_test_requires_in_test_package(self, client):
        """Test that tool requires can be listed as build and host requirements"""
        test = textwrap.dedent("""\
            from conan import ConanFile
            class Test(ConanFile):
                def build_requirements(self):
                    self.test_requires(self.tested_reference_str)
                def test(self):
                    pass
        """)

        client.save({"test_package/conanfile.py": test})
        client.run("create . -s:b os=Windows -s:h os=Linux --build=missing")
        for tool in "tool1", "tool2", "tool3", "tool4":
            client.assert_listed_require({f"{tool}/1.0": "Cache"}, build=True)
            assert f"{tool}/1.0: This is the binary for OS=Windows" in client.out
            assert f"{tool}/1.0: This is in context=build" in client.out
        client.assert_listed_require({"consumer/1.0": "Cache",
                                      "tool4/1.0": "Cache"})
        client.assert_listed_binary({"tool4/1.0": ("9a4eb3c8701508aa9458b1a73d0633783ecc2270",
                                                   "Build")})

        assert "tool4/1.0: This is the binary for OS=Linux" in client.out
        assert "tool4/1.0: This is in context=host" in client.out

        assert "consumer/1.0: HOST DEPS: [tool4/1.0]" in client.out
        assert "consumer/1.0: BUILD DEPS: [tool1/1.0, tool2/1.0, tool3/1.0, tool4/1.0]" in client.out
