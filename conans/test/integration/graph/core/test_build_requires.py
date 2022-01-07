import textwrap

import six
from parameterized import parameterized

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest
from conans.test.utils.tools import GenConanfile, TestClient


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

    def test_loop_build_require(self):
        # app -> lib -(br)-> tool ->|
        #          \<---------------|
        lib_ref = ConanFileReference.loads("lib/0.1@user/testing")
        tool_ref = ConanFileReference.loads("tool/0.1@user/testing")

        self._cache_recipe(tool_ref, GenConanfile().with_name("tool").with_version("0.1")
                                                   .with_require(lib_ref))
        self._cache_recipe(lib_ref, GenConanfile().with_name("lib").with_version("0.1")
                                                  .with_build_requires(tool_ref))

        with six.assertRaisesRegex(self, ConanException, "Loop detected in context host:"
                                                         " 'tool/0.1@user/testing' requires"
                                                         " 'lib/0.1@user/testing'"):
            self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                           .with_require(lib_ref))

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

    def test_conflict_transitive_build_requires(self):
        zlib_ref = ConanFileReference.loads("zlib/0.1@user/testing")
        zlib_ref2 = ConanFileReference.loads("zlib/0.2@user/testing")
        gtest_ref = ConanFileReference.loads("gtest/0.1@user/testing")
        lib_ref = ConanFileReference.loads("lib/0.1@user/testing")

        self._cache_recipe(zlib_ref, GenConanfile().with_name("zlib").with_version("0.1"))
        self._cache_recipe(zlib_ref2, GenConanfile().with_name("zlib").with_version("0.2"))

        self._cache_recipe(gtest_ref, GenConanfile().with_name("gtest").with_version("0.1")
                                                    .with_require(zlib_ref2))
        self._cache_recipe(lib_ref, GenConanfile().with_name("lib").with_version("0.1")
                                                  .with_require(zlib_ref)
                                                  .with_build_requires(gtest_ref))

        with six.assertRaisesRegex(self, ConanException,
                                   "Conflict in gtest/0.1@user/testing:\n"
                                   "    'gtest/0.1@user/testing' requires 'zlib/0.2@user/testing' "
                                   "while 'lib/0.1@user/testing' requires 'zlib/0.1@user/testing'."
                                   "\n    To fix this conflict you need to override the package "
                                   "'zlib' in your root package."):
            self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                           .with_require(lib_ref))

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

    def test_diamond_no_option_conflict_build_requires(self):
        # Same as above, but gtest->(build_require)->zlib2
        zlib_ref = ConanFileReference.loads("zlib/0.1@user/testing")
        gtest_ref = ConanFileReference.loads("gtest/0.1@user/testing")
        lib_ref = ConanFileReference.loads("lib/0.1@user/testing")

        self._cache_recipe(zlib_ref, GenConanfile().with_name("zlib").with_version("0.1")
                                                   .with_option("shared", [True, False])
                                                   .with_default_option("shared", False))

        self._cache_recipe(gtest_ref, GenConanfile().with_name("gtest").with_version("0.1")
                                                    .with_require(zlib_ref)
                                                    .with_default_option("zlib:shared", True))
        self._cache_recipe(lib_ref, GenConanfile().with_name("lib").with_version("0.1")
                                                  .with_require(zlib_ref)
                                                  .with_build_requires(gtest_ref))

        graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                               .with_require(lib_ref))

        self.assertEqual(4, len(graph.nodes))
        app = graph.root
        lib = app.dependencies[0].dst
        zlib = lib.dependencies[0].dst
        self.assertFalse(bool(zlib.conanfile.options.shared))
        gtest = lib.dependencies[1].dst
        zlib2 = gtest.dependencies[0].dst
        self.assertIs(zlib, zlib2)
        self._check_node(app, "app/0.1@", deps=[lib], build_deps=[], dependents=[],
                         closure=[lib, zlib])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[zlib], build_deps=[gtest],
                         dependents=[app], closure=[gtest, zlib])

        self._check_node(gtest, "gtest/0.1@user/testing#123", deps=[zlib2], build_deps=[],
                         dependents=[lib], closure=[zlib2])

    def test_diamond_option_conflict_build_requires(self):
        # Same as above, but gtest->(build_require)->zlib2
        zlib_ref = ConanFileReference.loads("zlib/0.1@user/testing")
        gtest_ref = ConanFileReference.loads("gtest/0.1@user/testing")
        lib_ref = ConanFileReference.loads("lib/0.1@user/testing")

        self._cache_recipe(zlib_ref, GenConanfile().with_name("zlib").with_version("0.1")
                                                   .with_option("shared", [True, False])
                                                   .with_default_option("shared", False))
        configure = """
    def configure(self):
        self.options["zlib"].shared=True
        """
        gtest = str(GenConanfile().with_name("gtest").with_version("0.1")
                                  .with_require(zlib_ref)) + configure
        self._cache_recipe(gtest_ref, gtest)
        self._cache_recipe(lib_ref, GenConanfile().with_name("lib").with_version("0.1")
                                                  .with_require(zlib_ref)
                                                  .with_build_requires(gtest_ref))

        with six.assertRaisesRegex(self, ConanException,
                                   "tried to change zlib/0.1@user/testing option shared to True"):
            self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                           .with_require(lib_ref))

    def test_consecutive_diamonds_build_requires(self):
        # app -> libe0.1 -------------> libd0.1 -> libb0.1 -------------> liba0.1
        #    \-(build-require)-> libf0.1 ->/    \-(build-require)->libc0.1 ->/
        liba_ref = ConanFileReference.loads("liba/0.1@user/testing")
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")
        libc_ref = ConanFileReference.loads("libc/0.1@user/testing")
        libd_ref = ConanFileReference.loads("libd/0.1@user/testing")
        libe_ref = ConanFileReference.loads("libe/0.1@user/testing")
        libf_ref = ConanFileReference.loads("libf/0.1@user/testing")
        self._cache_recipe(liba_ref, GenConanfile().with_name("liba").with_version("0.1"))
        self._cache_recipe(libb_ref, GenConanfile().with_name("libb").with_version("0.1")
                                                   .with_require(liba_ref))
        self._cache_recipe(libc_ref, GenConanfile().with_name("libc").with_version("0.1")
                                                   .with_require(liba_ref))
        self._cache_recipe(libd_ref, GenConanfile().with_name("libd").with_version("0.1")
                                                   .with_require(libb_ref)
                                                   .with_build_requires(libc_ref))
        self._cache_recipe(libe_ref, GenConanfile().with_name("libe").with_version("0.1")
                                                   .with_require(libd_ref))
        self._cache_recipe(libf_ref, GenConanfile().with_name("libf").with_version("0.1")
                                                   .with_require(libd_ref))
        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(libe_ref)
                                                    .with_build_requires(libf_ref))

        self.assertEqual(7, len(deps_graph.nodes))
        app = deps_graph.root
        libe = app.dependencies[0].dst
        libf = app.dependencies[1].dst
        libd = libe.dependencies[0].dst
        libb = libd.dependencies[0].dst
        libc = libd.dependencies[1].dst
        liba = libc.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[libe], build_deps=[libf], dependents=[],
                         closure=[libf, libe, libd, libb, liba])
        self._check_node(libe, "libe/0.1@user/testing#123", deps=[libd], build_deps=[],
                         dependents=[app], closure=[libd, libb, liba])
        self._check_node(libf, "libf/0.1@user/testing#123", deps=[libd], build_deps=[],
                         dependents=[app], closure=[libd, libb, liba])
        self._check_node(libd, "libd/0.1@user/testing#123", deps=[libb], build_deps=[libc],
                         dependents=[libe, libf], closure=[libc, libb, liba])
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[libd], closure=[liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[libd], closure=[liba])
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb, libc], closure=[])

    def test_parallel_diamond_build_requires(self):
        # app --------> libb0.1 ---------> liba0.1
        #    \--------> libc0.1 ----------->/
        #    \-(build_require)-> libd0.1 ->/
        liba_ref = ConanFileReference.loads("liba/0.1@user/testing")
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")
        libc_ref = ConanFileReference.loads("libc/0.1@user/testing")
        libd_ref = ConanFileReference.loads("libd/0.1@user/testing")
        self._cache_recipe(liba_ref, GenConanfile().with_name("liba").with_version("0.1"))
        self._cache_recipe(libb_ref, GenConanfile().with_name("libb").with_version("0.1")
                                                   .with_require(liba_ref))
        self._cache_recipe(libc_ref, GenConanfile().with_name("libc").with_version("0.1")
                                                   .with_require(liba_ref))
        self._cache_recipe(libd_ref, GenConanfile().with_name("libd").with_version("0.1")
                                                   .with_require(liba_ref))
        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(libb_ref)
                                                    .with_require(libc_ref)
                                                    .with_build_requires(libd_ref))

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        libd = app.dependencies[2].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[libb, libc], build_deps=[libd],
                         dependents=[], closure=[libd, libb, libc, liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba])
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba])
        self._check_node(libd, "libd/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba])
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb, libc, libd], closure=[])

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

    def test_build_require_conflict(self):
        # https://github.com/conan-io/conan/issues/4931
        # cheetah -> gazelle -> grass
        #    \--(br)------0.2----/
        grass01_ref = ConanFileReference.loads("grass/0.1@user/testing")
        grass02_ref = ConanFileReference.loads("grass/0.2@user/testing")
        gazelle_ref = ConanFileReference.loads("gazelle/0.1@user/testing")

        self._cache_recipe(grass01_ref, GenConanfile().with_name("grass").with_version("0.1"))
        self._cache_recipe(grass02_ref, GenConanfile().with_name("grass").with_version("0.2"))
        self._cache_recipe(gazelle_ref, GenConanfile().with_name("gazelle").with_version("0.1")
                                                      .with_require(grass01_ref))

        with six.assertRaisesRegex(self, ConanException,
                                   "Conflict in cheetah/0.1:\n"
                                   "    'cheetah/0.1' requires 'grass/0.2@user/testing' while "
                                   "'gazelle/0.1@user/testing' requires 'grass/0.1@user/testing'.\n"
                                   "    To fix this conflict you need to override the package "
                                   "'grass' in your root package."):
            self.build_graph(GenConanfile().with_name("cheetah").with_version("0.1")
                                           .with_require(gazelle_ref)
                                           .with_build_requires(grass02_ref))

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

        self._check_node(cheetah, "cheetah/0.1@", deps=[gazelle], build_deps=[grass2],
                         dependents=[], closure=[gazelle, grass])
        self.assertListEqual(list(cheetah.conanfile.deps_cpp_info.libs),
                             ['mylibgazelle0.1lib', 'mylibgrass0.1lib'])

    def test_test_require(self):
        # app -(tr)-> gtest/0.1
        # This test should survive in 2.0
        tool_ref = ConanFileReference.loads("gtest/0.1")
        self._cache_recipe(tool_ref, GenConanfile("gtest", "0.1"))

        conanfile = textwrap.dedent("""
            from conans import ConanFile
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

        self._check_node(app, "app/0.1@", deps=[], build_deps=[tool], dependents=[],
                         closure=[tool])
        self._check_node(tool, "gtest/0.1#123", deps=[], build_deps=[],
                         dependents=[app], closure=[])


def test_tool_requires():
    """Testing temporary tool_requires attribute being "an alias" of build_require and
    introduced to provide a compatible recipe with 2.0. At 2.0, the meaning of a build require being
    a 'tool' will be a tool_require."""

    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . tool1/1.0@")
    client.run("create . tool2/1.0@")
    client.run("create . tool3/1.0@")
    client.run("create . tool4/1.0@")

    consumer = textwrap.dedent("""
        from conans import ConanFile
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
    client.run("create . consumer/1.0@")
    assert """Build requirements
    tool1/1.0 from local cache - Cache
    tool2/1.0 from local cache - Cache
    tool3/1.0 from local cache - Cache
    tool4/1.0 from local cache - Cache""" in client.out
