import textwrap

import pytest

from parameterized import parameterized

from conans.client.graph.graph_error import GraphConflictError, GraphLoopError, GraphRuntimeError
from conans.model.recipe_ref import RecipeReference
from test.integration.graph.core.graph_manager_base import GraphManagerTest
from conan.test.utils.tools import GenConanfile, NO_SETTINGS_PACKAGE_ID, TestClient


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

        assert type(deps_graph.error) == GraphRuntimeError

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

    def test_build_require_conflict(self):
        # https://github.com/conan-io/conan/issues/4931
        # cheetah -> gazelle -> grass/0.1
        #    \--(br)----------> grass/0.2

        self._cache_recipe("grass/0.1", GenConanfile())
        self._cache_recipe("grass/0.2", GenConanfile())
        self._cache_recipe("gazelle/0.1", GenConanfile().with_require("grass/0.1"))

        deps_graph = self.build_graph(GenConanfile("cheetah", "0.1")
                                      .with_require("gazelle/0.1")
                                      .with_tool_requires("grass/0.2"))

        self.assertEqual(4, len(deps_graph.nodes))
        cheetah = deps_graph.root
        gazelle = cheetah.dependencies[0].dst
        grass2 = cheetah.dependencies[1].dst
        grass1 = gazelle.dependencies[0].dst
        self._check_node(cheetah, "cheetah/0.1", deps=[gazelle, grass2])
        self._check_node(gazelle, "gazelle/0.1#123", deps=[grass1], dependents=[cheetah])
        self._check_node(grass1, "grass/0.1#123", deps=[], dependents=[gazelle])
        self._check_node(grass2, "grass/0.2#123", dependents=[cheetah])


class TestBuildRequiresVisible(GraphManagerTest):

    def test_visible_build(self):
        self._cache_recipe("liba/0.1", GenConanfile())
        self._cache_recipe("libb/0.1", GenConanfile().with_requirement("liba/0.1", build=True))
        self._cache_recipe("libc/0.1", GenConanfile().with_requirement("libb/0.1", visible=False))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_require("libc/0.1"))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[libc], dependents=[])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", deps=[], dependents=[libb])

        # node, include, link, build, run
        _check_transitive(app, [(libc, True, True, False, False)])
        _check_transitive(libc, [(libb, True, True, False, False),
                                 (liba, False, False, True, False)])  # liba is build & visible!
        _check_transitive(libb, [(liba, True, True, True, False)])


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

    def test_test_require_loop(self):
        # https://github.com/conan-io/conan/issues/15412
        self._cache_recipe("gtest/1.11", GenConanfile())
        self._cache_recipe("abseil/1.0", GenConanfile().with_test_requires("gtest/[>=1 <1.14]"))
        self._cache_recipe("gtest/1.14", GenConanfile().with_requires("abseil/1.0"))
        deps_graph = self.build_graph(GenConanfile("opencv", "1.0").with_test_requires("gtest/1.14"))

        self.assertEqual(4, len(deps_graph.nodes))
        opencv = deps_graph.root
        gtest14 = opencv.dependencies[0].dst
        abseil = gtest14.dependencies[0].dst
        gtest11 = abseil.dependencies[0].dst

        self._check_node(opencv, "opencv/1.0@", deps=[gtest14], dependents=[])
        self._check_node(gtest14, "gtest/1.14#123", deps=[abseil], dependents=[opencv])
        self._check_node(abseil, "abseil/1.0#123", deps=[gtest11], dependents=[gtest14])
        self._check_node(gtest11, "gtest/1.11#123", deps=[], dependents=[abseil])


class TestTestRequiresProblemsShared(GraphManagerTest):

    def _check_graph(self, deps_graph, reverse):
        self.assertEqual(3, len(deps_graph.nodes))
        lib_c = deps_graph.root
        if not reverse:
            lib_a = lib_c.dependencies[0].dst
            util = lib_a.dependencies[0].dst
            util2 = lib_c.dependencies[1].dst
        else:
            util = lib_c.dependencies[0].dst
            lib_a = lib_c.dependencies[1].dst
            util2 = lib_a.dependencies[0].dst
        assert util is util2

        self._check_node(lib_c, "lib_c/0.1@", deps=[lib_a, util], dependents=[])
        self._check_node(lib_a, "lib_a/0.1#123", deps=[util], dependents=[lib_c])
        self._check_node(util, "util/0.1#123", deps=[], dependents=[lib_a, lib_c])

        # node, include, link, build, run
        _check_transitive(lib_c, [(lib_a, True, True, False, True),
                                  (util, True, True, False, True)])

    @parameterized.expand([(True,), (False,)])
    def test_fixed_versions(self, reverse):
        #  lib_c -(tr)-> lib_a -0.1--> util
        #    \--------(tr)----0.1------/
        # if versions exactly match, it shouldn't be an issue
        self._cache_recipe("util/0.1", GenConanfile().with_package_type("shared-library"))
        self._cache_recipe("lib_a/0.1", GenConanfile().with_requires("util/0.1")
                                                      .with_package_type("shared-library"))
        deps = ("lib_a/0.1", "util/0.1") if not reverse else ("util/0.1", "lib_a/0.1")
        deps_graph = self.build_graph(GenConanfile("lib_c", "0.1").with_test_requires(*deps))
        self._check_graph(deps_graph, reverse)

    @parameterized.expand([(True,), (False,)])
    def test_fixed_versions_conflict(self, reverse):
        #  lib_c -(tr)-> lib_a -0.1--> util
        #    \--------(tr)----0.2------/
        # This should be a a conflict of versions
        self._cache_recipe("util/0.1", GenConanfile().with_package_type("shared-library"))
        self._cache_recipe("util/0.2", GenConanfile().with_package_type("shared-library"))
        self._cache_recipe("lib_a/0.1", GenConanfile().with_requires("util/0.1")
                                                      .with_package_type("shared-library"))
        deps = ("lib_a/0.1", "util/0.2") if not reverse else ("util/0.2", "lib_a/0.1")
        conanfile = GenConanfile("lib_c", "0.1").with_test_requires(*deps)
        deps_graph = self.build_graph(conanfile, install=False)
        assert type(deps_graph.error) == GraphConflictError

    @parameterized.expand([(True,), (False,)])
    def test_fixed_versions_hybrid(self, reverse):
        #  lib_c -----> lib_a--0.1--> util
        #    \--------(tr)----0.1------/
        # mixing requires + test_requires, should work
        self._cache_recipe("util/0.1", GenConanfile().with_package_type("shared-library"))
        self._cache_recipe("util/0.2", GenConanfile().with_package_type("shared-library"))
        self._cache_recipe("lib_a/0.1", GenConanfile().with_requires("util/0.1")
                                                      .with_package_type("shared-library"))
        conanfile = GenConanfile("lib_c", "0.1")
        if not reverse:
            conanfile = conanfile.with_requires("lib_a/0.1").with_test_requires("util/0.1")
        else:
            conanfile = conanfile.with_test_requires("lib_a/0.1").with_requires("util/0.1")
        deps_graph = self.build_graph(conanfile)
        self._check_graph(deps_graph, reverse=reverse)

    @parameterized.expand([(True,), (False,)])
    def test_fixed_versions_hybrid_conflict(self, reverse):
        #  lib_c -----> lib_a--0.1---> util
        #    \--------(tr)----0.2------/
        # Same as above, but mixing regular requires with test_requires
        self._cache_recipe("util/0.1", GenConanfile().with_package_type("shared-library"))
        self._cache_recipe("util/0.2", GenConanfile().with_package_type("shared-library"))
        self._cache_recipe("lib_a/0.1", GenConanfile().with_requires("util/0.1")
                                                      .with_package_type("shared-library"))
        conanfile = GenConanfile("lib_c", "0.1")
        if not reverse:
            conanfile = conanfile.with_requires("lib_a/0.1").with_test_requires("util/0.2")
        else:
            conanfile = conanfile.with_test_requires("lib_a/0.1").with_requires("util/0.2")
        deps_graph = self.build_graph(conanfile, install=False)
        assert type(deps_graph.error) == GraphConflictError

    @parameterized.expand([(True,), (False,)])
    def test_version_ranges(self, reverse):
        #  lib_c -(tr)-> lib_a -> util
        #    \--------(tr)-------/
        self._cache_recipe("util/0.1", GenConanfile().with_package_type("shared-library"))
        self._cache_recipe("lib_a/0.1", GenConanfile().with_requires("util/[>=0.1 <1]")
                                                      .with_package_type("shared-library"))

        deps = ("lib_a/[>=0]", "util/[>=0]") if not reverse else ("util/[>=0]", "lib_a/[>=0]")
        deps_graph = self.build_graph(GenConanfile("lib_c", "0.1").with_test_requires(*deps))
        self._check_graph(deps_graph, reverse)

    @parameterized.expand([(True,), (False,)])
    def test_version_ranges_conflict(self, reverse):
        #  lib_c -(tr)-> lib_a -> util/0.1
        #    \--------(tr)------> util/1.0
        self._cache_recipe("util/0.1", GenConanfile().with_package_type("shared-library"))
        self._cache_recipe("util/1.0", GenConanfile().with_package_type("shared-library"))
        self._cache_recipe("lib_a/0.1", GenConanfile().with_requires("util/[>=0.1 <1]")
                                                      .with_package_type("shared-library"))
        deps = ("lib_a/[>=0]", "util/[>=1]") if not reverse else ("util/[>=1]", "lib_a/[>=0]")
        deps_graph = self.build_graph(GenConanfile("lib_c", "0.1").with_test_requires(*deps),
                                      install=False)
        assert type(deps_graph.error) == GraphConflictError

    @parameterized.expand([(True,), (False,)])
    def test_version_ranges_hybrid(self, reverse):
        #  lib_c ---> lib_a -> util
        #    \--------(tr)-------/
        self._cache_recipe("util/0.1", GenConanfile().with_package_type("shared-library"))
        self._cache_recipe("lib_a/0.1", GenConanfile().with_requires("util/[>=0.1 <1]")
                           .with_package_type("shared-library"))

        conanfile = GenConanfile("lib_c", "0.1")
        if not reverse:
            conanfile = conanfile.with_requires("lib_a/[>=0.1]").with_test_requires("util/[>=0.1]")
        else:
            conanfile = conanfile.with_test_requires("lib_a/[>=0.1]").with_requires("util/[>=0.1]")
        deps_graph = self.build_graph(conanfile)
        self._check_graph(deps_graph, reverse)

    @parameterized.expand([(True,), (False,)])
    def test_version_ranges_hybrid_conflict(self, reverse):
        #  lib_c -(tr)-> lib_a -> util/0.1
        #    \--------(tr)------> util/1.0
        self._cache_recipe("util/0.1", GenConanfile().with_package_type("shared-library"))
        self._cache_recipe("util/1.0", GenConanfile().with_package_type("shared-library"))
        self._cache_recipe("lib_a/0.1", GenConanfile().with_requires("util/[>=0.1 <1]")
                           .with_package_type("shared-library"))
        conanfile = GenConanfile("lib_c", "0.1")
        if not reverse:
            conanfile = conanfile.with_requires("lib_a/[>=0.1]").with_test_requires("util/[>=1]")
        else:
            conanfile = conanfile.with_test_requires("lib_a/[>=0.1]").with_requires("util/[>=1]")
        deps_graph = self.build_graph(conanfile, install=False)
        assert type(deps_graph.error) == GraphConflictError


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
                                (cmake, False, False, True, True)])

    def test_deep_dependency_tree(self):
        # app -> liba -> libb-(br public) -> sfun -> libsfun -> libx -> liby -> libz
        #                    -(normal req) -> libsfun -> libx -> liby -> libz
        self.recipe_conanfile("libz/0.1", GenConanfile())
        self.recipe_conanfile("liby/0.1", GenConanfile().with_requirement("libz/0.1", run=True))
        self.recipe_conanfile("libx/0.1", GenConanfile().with_requirement("liby/0.1", run=True))
        self.recipe_conanfile("libsfun/0.1", GenConanfile().with_requirement("libx/0.1", run=True))
        self.recipe_conanfile("sfun/0.1", GenConanfile().with_requirement("libsfun/0.1", run=True))
        self.recipe_conanfile("libb/0.1", GenConanfile()
                              .with_tool_requirement("sfun/0.1", visible=True)
                              .with_requirement("libsfun/0.1", run=True))
        self.recipe_conanfile("liba/0.1", GenConanfile().with_requirement("libb/0.1", run=True))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_requirement("liba/0.1", run=True))

        # Build requires always apply to the consumer
        self.assertEqual(8 + 4, len(deps_graph.nodes))
        app = deps_graph.root
        liba = app.dependencies[0].dst
        libb = liba.dependencies[0].dst
        libsfun = libb.dependencies[0].dst
        libx = libsfun.dependencies[0].dst
        liby = libx.dependencies[0].dst
        libz = liby.dependencies[0].dst
        sfun = libb.dependencies[1].dst
        libsfun_build = sfun.dependencies[0].dst
        libx_build = libsfun_build.dependencies[0].dst
        liby_build = libx_build.dependencies[0].dst
        libz_build = liby_build.dependencies[0].dst

        # TODO non-build-requires

        self._check_node(app, "app/0.1@", deps=[liba], dependents=[])
        self._check_node(liba, "liba/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[sfun, libsfun], dependents=[liba])
        self._check_node(sfun, "sfun/0.1#123", deps=[libsfun_build], dependents=[libb])
        self._check_node(libsfun_build, "libsfun/0.1#123", deps=[libx_build], dependents=[sfun])
        self._check_node(libx_build, "libx/0.1#123", deps=[liby_build], dependents=[libsfun_build])
        self._check_node(liby_build, "liby/0.1#123", deps=[libz_build], dependents=[libx_build])
        self._check_node(libz_build, "libz/0.1#123", deps=[], dependents=[liby_build])

        # node, include, link, build, run
        _check_transitive(liby_build, [(libz_build, True, True, False, True)])
        _check_transitive(libx_build, [(liby_build, True, True, False, True),
                                       (libz_build, True, True, False, True)])
        _check_transitive(libsfun_build, [(libx_build, True, True, False, True),
                                          (liby_build, True, True, False, True),
                                          (libz_build, True, True, False, True)])
        _check_transitive(sfun, [(libsfun_build, True, True, False, True),
                                 (libx_build, True, True, False, True),
                                 (liby_build, True, True, False, True),
                                 (libz_build, True, True, False, True)])
        _check_transitive(libb, [(libsfun, True, True, False, True),
                                 (libx, True, True, False, True),
                                 (liby, True, True, False, True),
                                 (libz, True, True, False, True),
                                 (sfun, False, False, True, True),
                                 (libsfun_build, False, False, True, True),
                                 (libx_build, False, False, True, True),
                                 (liby_build, False, False, True, True),
                                 (libz_build, False, False, True, True)])
        _check_transitive(liba, [(libb, True, True, False, True),
                                 (libsfun, True, True, False, True),
                                 (libx, True, True, False, True),
                                 (liby, True, True, False, True),
                                 (libz, True, True, False, True),
                                 (sfun, False, False, True, True),
                                 (libsfun_build, False, False, True, True),
                                 (libx_build, False, False, True, True),
                                 (liby_build, False, False, True, True),
                                 (libz_build, False, False, True, True)])
        _check_transitive(app, [(liba, True, True, False, True),
                                (libb, True, True, False, True),
                                (libsfun, True, True, False, True),
                                (libx, True, True, False, True),
                                (liby, True, True, False, True),
                                (libz, True, True, False, True),
                                (sfun, False, False, True, True),
                                (libsfun_build, False, False, True, True),
                                (libx_build, False, False, True, True),
                                (liby_build, False, False, True, True),
                                (libz_build, False, False, True, True)])

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

        assert type(deps_graph.error) == GraphConflictError

        # Build requires always apply to the consumer
        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        cmake1 = libb.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[libb, libc], dependents=[])
        self._check_node(libb, "libb/0.1#123", deps=[cmake1], dependents=[app])
        self._check_node(cmake1, "cmake/0.1#123", deps=[], dependents=[libb])

    def test_conflict_diamond_two_levels(self):
        # app -> libd -> libb -(br public)-> cmake/0.1
        #   \--> libe -> libc -(br public)-> cmake/0.2
        self.recipe_conanfile("cmake/0.1", GenConanfile())
        self.recipe_conanfile("cmake/0.2", GenConanfile())
        self.recipe_conanfile("libb/0.1",
                              GenConanfile().with_tool_requirement("cmake/0.1", visible=True))
        self.recipe_conanfile("libc/0.1",
                              GenConanfile().with_tool_requirement("cmake/0.2", visible=True))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_requires("libb/0.1"))
        self.recipe_conanfile("libe/0.1", GenConanfile().with_requires("libc/0.1"))

        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_requires("libd/0.1",
                                                                               "libe/0.1"),
                                      install=False)

        assert type(deps_graph.error) == GraphConflictError

        # Build requires always apply to the consumer
        self.assertEqual(6, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libe = app.dependencies[1].dst
        libb = libd.dependencies[0].dst
        libc = libe.dependencies[0].dst
        cmake1 = libb.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[libd, libe], dependents=[])
        self._check_node(libd, "libd/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libe, "libe/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[cmake1], dependents=[libd])
        self._check_node(libc, "libc/0.1#123", deps=[], dependents=[libe])
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
                                (protobuf_build, False, False, True, True)])

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
                                (protobuf_build, False, False, True, True)])
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

        assert type(deps_graph.error) == GraphLoopError

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

        assert type(deps_graph.error) == GraphLoopError

        # Build requires always apply to the consumer
        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        cmake = app.dependencies[0].dst
        gtest = cmake.dependencies[0].dst
        cmake2 = gtest.dependencies[0].dst

        assert deps_graph.error.ancestor == cmake
        assert deps_graph.error.node == cmake2

    def test_infinite_recursion_test(self):
        """Ensure that direct conflicts in a node are properly reported and Conan does not loop"""
        tc = TestClient(light=True)
        tc.save({"conanfile.py": GenConanfile("app").with_package_type("application")})
        tc.run("create . --version=1.0 --build-require")
        tc.run("create . --version=1.1 --build-require")
        tc.run("graph info --tool-requires=app/1.1 --tool-requires=app/1.0", assert_error=True)
        assert "Duplicated requirement: app/1.0" in tc.out


def test_tool_requires():
    """Testing temporary tool_requires attribute being "an alias" of build_require and
    introduced to provide a compatible recipe with 2.0. At 2.0, the meaning of a build require being
    a 'tool' will be a tool_require."""

    client = TestClient(light=True)
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
