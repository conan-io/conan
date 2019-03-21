from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_INCACHE
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.test.functional.graph.graph_manager_base import GraphManagerTest
from conans.test.utils.conanfile import TestConanFile
from parameterized import parameterized


class TransitiveGraphTest(GraphManagerTest):
    def test_basic(self):
        # say/0.1
        deps_graph = self.build_graph(TestConanFile("Say", "0.1"))
        self.assertEqual(1, len(deps_graph.nodes))
        node = deps_graph.root
        self.assertEqual(node.conanfile.name, "Say")
        self.assertEqual(len(node.dependencies), 0)
        self.assertEqual(len(node.dependants), 0)

    def test_transitive(self):
        # app -> libb0.1
        libb_ref = "libb/0.1@user/testing"
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1"))
        deps_graph = self.build_graph(TestConanFile("app", "0.1",
                                                    requires=[libb_ref]))
        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        self.assertEqual(app.conanfile.name, "app")
        self.assertEqual(len(app.dependencies), 1)
        self.assertEqual(len(app.dependants), 0)
        self.assertEqual(app.recipe, RECIPE_CONSUMER)

        libb = app.dependencies[0].dst
        self.assertEqual(libb.conanfile.name, "libb")
        self.assertEqual(len(libb.dependencies), 0)
        self.assertEqual(len(libb.dependants), 1)
        self.assertEqual(libb.inverse_neighbors(), [app])
        self.assertEqual(libb.ancestors, set([app.ref.name]))
        self.assertEqual(libb.recipe, RECIPE_INCACHE)

        self.assertEqual(app.public_closure, [libb])
        self.assertEqual(libb.public_closure, [])
        self.assertEqual(app.public_deps, {"app": app, "libb": libb})
        self.assertEqual(libb.public_deps, app.public_deps)

    def test_transitive_two_levels(self):
        # app -> libb0.1 -> liba0.1
        liba_ref = "liba/0.1@user/testing"
        libb_ref = "libb/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1"))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        deps_graph = self.build_graph(TestConanFile("app", "0.1", requires=[libb_ref]))

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        # No Revision??? Because of consumer?
        self._check_node(app, "app/0.1@None/None", deps=[libb], build_deps=[], dependents=[],
                         closure=[libb, liba], public_deps=[app, libb, liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba], public_deps=[app, libb, liba])
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb], closure=[], public_deps=[app, libb, liba])

    def test_diamond(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 ->/
        liba_ref = "liba/0.1@user/testing"
        libb_ref = "libb/0.1@user/testing"
        libc_ref = "libc/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1"))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        self._cache_recipe(libc_ref, TestConanFile("libc", "0.1", requires=[liba_ref]))
        deps_graph = self.build_graph(TestConanFile("app", "0.1", requires=[libb_ref, libc_ref]))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        # No Revision??? Because of consumer?
        self._check_node(app, "app/0.1@None/None", deps=[libb, libc], build_deps=[], dependents=[],
                         closure=[libb, libc, liba], public_deps=[app, libb, libc, liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba], public_deps=[app, libb, libc, liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba], public_deps=[app, libb, libc, liba])
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb, libc], closure=[], public_deps=[app, libb, libc, liba])

    def test_consecutive_diamonds(self):
        # app -> libe0.1 -> libd0.1 -> libb0.1 -> liba0.1
        #    \-> libf0.1 ->/    \-> libc0.1 ->/
        liba_ref = "liba/0.1@user/testing"
        libb_ref = "libb/0.1@user/testing"
        libc_ref = "libc/0.1@user/testing"
        libd_ref = "libd/0.1@user/testing"
        libe_ref = "libe/0.1@user/testing"
        libf_ref = "libf/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1"))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        self._cache_recipe(libc_ref, TestConanFile("libc", "0.1", requires=[liba_ref]))
        self._cache_recipe(libd_ref, TestConanFile("libd", "0.1", requires=[libb_ref, libc_ref]))
        self._cache_recipe(libe_ref, TestConanFile("libe", "0.1", requires=[libd_ref]))
        self._cache_recipe(libf_ref, TestConanFile("libf", "0.1", requires=[libd_ref]))
        deps_graph = self.build_graph(TestConanFile("app", "0.1", requires=[libe_ref, libf_ref]))

        self.assertEqual(7, len(deps_graph.nodes))
        app = deps_graph.root
        libe = app.dependencies[0].dst
        libf = app.dependencies[1].dst
        libd = libe.dependencies[0].dst
        libb = libd.dependencies[0].dst
        libc = libd.dependencies[1].dst
        liba = libc.dependencies[0].dst

        public_deps = [app, libb, libc, liba, libd, libe, libf]
        self._check_node(app, "app/0.1@None/None", deps=[libe, libf], build_deps=[], dependents=[],
                         closure=[libe, libf, libd, libb, libc, liba], public_deps=public_deps)
        self._check_node(libe, "libe/0.1@user/testing#123", deps=[libd], build_deps=[],
                         dependents=[app], closure=[libd, libb, libc, liba],
                         public_deps=public_deps)
        self._check_node(libf, "libf/0.1@user/testing#123", deps=[libd], build_deps=[],
                         dependents=[app], closure=[libd, libb, libc, liba],
                         public_deps=public_deps)
        self._check_node(libd, "libd/0.1@user/testing#123", deps=[libb, libc], build_deps=[],
                         dependents=[libe, libf], closure=[libb, libc, liba],
                         public_deps=public_deps)
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[libd], closure=[liba], public_deps=public_deps)
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[libd], closure=[liba], public_deps=public_deps)
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb, libc], closure=[], public_deps=public_deps)

    def test_parallel_diamond(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 ->/
        #    \-> libd0.1 ->/
        liba_ref = "liba/0.1@user/testing"
        libb_ref = "libb/0.1@user/testing"
        libc_ref = "libc/0.1@user/testing"
        libd_ref = "libd/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1"))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        self._cache_recipe(libc_ref, TestConanFile("libc", "0.1", requires=[liba_ref]))
        self._cache_recipe(libd_ref, TestConanFile("libd", "0.1", requires=[liba_ref]))
        deps_graph = self.build_graph(TestConanFile("app", "0.1",
                                                    requires=[libb_ref, libc_ref, libd_ref]))

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        libd = app.dependencies[2].dst
        liba = libb.dependencies[0].dst

        public_deps = [app, libb, libc, liba, libd]
        self._check_node(app, "app/0.1@None/None", deps=[libb, libc, libd], build_deps=[],
                         dependents=[], closure=[libb, libc, libd, liba], public_deps=public_deps)
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba], public_deps=public_deps)
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba], public_deps=public_deps)
        self._check_node(libd, "libd/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba], public_deps=public_deps)
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb, libc, libd], closure=[], public_deps=public_deps)

    def test_nested_diamond(self):
        # app --------> libb0.1 -> liba0.1
        #    \--------> libc0.1 ->/
        #     \-> libd0.1 ->/
        liba_ref = "liba/0.1@user/testing"
        libb_ref = "libb/0.1@user/testing"
        libc_ref = "libc/0.1@user/testing"
        libd_ref = "libd/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1"))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        self._cache_recipe(libc_ref, TestConanFile("libc", "0.1", requires=[liba_ref]))
        self._cache_recipe(libd_ref, TestConanFile("libd", "0.1", requires=[libc_ref]))
        deps_graph = self.build_graph(TestConanFile("app", "0.1",
                                                    requires=[libb_ref, libc_ref, libd_ref]))

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        libd = app.dependencies[2].dst
        liba = libb.dependencies[0].dst

        public_deps = [app, libb, libc, liba, libd]
        self._check_node(app, "app/0.1@None/None", deps=[libb, libc, libd], build_deps=[],
                         dependents=[], closure=[libb, libd, libc, liba], public_deps=public_deps)
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba], public_deps=public_deps)
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app, libd], closure=[liba], public_deps=public_deps)
        self._check_node(libd, "libd/0.1@user/testing#123", deps=[libc], build_deps=[],
                         dependents=[app], closure=[libc, liba], public_deps=public_deps)
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb, libc], closure=[], public_deps=public_deps)

    def test_multiple_transitive(self):
        # https://github.com/conanio/conan/issues/4720
        # app -> libb0.1  -> libc0.1 -> libd0.1
        #    \--------------->/          /
        #     \------------------------>/
        libb_ref = "libb/0.1@user/testing"
        libc_ref = "libc/0.1@user/testing"
        libd_ref = "libd/0.1@user/testing"
        self._cache_recipe(libd_ref, TestConanFile("libd", "0.1"))
        self._cache_recipe(libc_ref, TestConanFile("libc", "0.1", requires=[libd_ref]))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[libc_ref]))
        deps_graph = self.build_graph(TestConanFile("liba", "0.1",
                                                    requires=[libd_ref, libc_ref, libb_ref]))

        self.assertEqual(4, len(deps_graph.nodes))
        liba = deps_graph.root
        libd = liba.dependencies[0].dst
        libc = liba.dependencies[1].dst
        libb = liba.dependencies[2].dst

        self._check_node(libd, "libd/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[liba, libc], closure=[], public_deps=[liba, libb, libc, libd])
        self._check_node(liba, "liba/0.1@None/None", deps=[libd, libc, libb], build_deps=[],
                         dependents=[],
                         closure=[libb, libc, libd], public_deps=[liba, libb, libc, libd])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[libc], build_deps=[],
                         dependents=[liba], closure=[libc, libd],
                         public_deps=[liba, libb, libc, libd])
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[libd], build_deps=[],
                         dependents=[liba, libb], closure=[libd],
                         public_deps=[liba, libb, libc, libd])

    def test_diamond_conflict(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 -> liba0.2
        liba_ref = "liba/0.1@user/testing"
        liba_ref2 = "liba/0.2@user/testing"
        libb_ref = "libb/0.1@user/testing"
        libc_ref = "libc/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1"))
        self._cache_recipe(liba_ref2, TestConanFile("liba", "0.2"))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        self._cache_recipe(libc_ref, TestConanFile("libc", "0.1", requires=[liba_ref2]))
        with self.assertRaisesRegexp(ConanException, "Requirement liba/0.2@user/testing conflicts"):
            self.build_graph(TestConanFile("app", "0.1", requires=[libb_ref, libc_ref]))

    def test_loop(self):
        # app -> libc0.1 -> libb0.1 -> liba0.1 ->|
        #             \<-------------------------|
        liba_ref = "liba/0.1@user/testing"
        libb_ref = "libb/0.1@user/testing"
        libc_ref = "libc/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1", requires=[libc_ref]))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        self._cache_recipe(libc_ref, TestConanFile("libc", "0.1", requires=[libb_ref]))
        with self.assertRaisesRegexp(ConanException, "Loop detected: 'liba/0.1@user/testing' "
                                     "requires 'libc/0.1@user/testing'"):
            self.build_graph(TestConanFile("app", "0.1", requires=[libc_ref]))

    def test_self_loop(self):
        ref1 = "base/1.0@user/testing"
        self._cache_recipe(ref1, TestConanFile("base", "0.1"))
        ref = ConanFileReference.loads("base/aaa@user/testing")
        with self.assertRaisesRegexp(ConanException, "Loop detected: 'base/aaa@user/testing' "
                                     "requires 'base/aaa@user/testing'"):
            self.build_graph(TestConanFile("base", "aaa", requires=[ref1]), ref=ref, create_ref=ref)

    @parameterized.expand([("recipe", ), ("profile", )])
    def test_basic_build_require(self, build_require):
        # app -(br)-> tool0.1
        self._cache_recipe("tool/0.1@user/testing", TestConanFile("tool", "0.1"))
        if build_require == "recipe":
            deps_graph = self.build_graph(TestConanFile("app", "0.1",
                                                        build_requires=["tool/0.1@user/testing"]))
        else:
            profile_build_requires = {"*": [ConanFileReference.loads("tool/0.1@user/testing")]}
            deps_graph = self.build_graph(TestConanFile("app", "0.1"),
                                          profile_build_requires=profile_build_requires)

        # Build requires always apply to the consumer
        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        tool = app.dependencies[0].dst

        self._check_node(app, "app/0.1@None/None", deps=[], build_deps=[tool], dependents=[],
                         closure=[tool], public_deps=[app])
        self._check_node(tool, "tool/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[app], closure=[], public_deps=[tool, app])

    def test_transitive_build_require_recipe(self):
        # app -> lib -(br)-> tool
        self._cache_recipe("tool/0.1@user/testing", TestConanFile("tool", "0.1"))
        self._cache_recipe("lib/0.1@user/testing",
                           TestConanFile("lib", "0.1",
                                         build_requires=["tool/0.1@user/testing"]))
        deps_graph = self.build_graph(TestConanFile("app", "0.1",
                                                    requires=["lib/0.1@user/testing"]))

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        tool = lib.dependencies[0].dst

        self._check_node(app, "app/0.1@None/None", deps=[lib], build_deps=[], dependents=[],
                         closure=[lib], public_deps=[app, lib])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[], build_deps=[tool],
                         dependents=[app], closure=[tool], public_deps=[app, lib])

        self._check_node(tool, "tool/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[lib], closure=[], public_deps=[tool, lib])

    def test_loop_build_require(self):
        # app -> lib -(br)-> tool ->|
        #          \<---------------|
        lib_ref = "lib/0.1@user/testing"
        self._cache_recipe("tool/0.1@user/testing", TestConanFile("tool", "0.1", requires=[lib_ref]))
        self._cache_recipe(lib_ref,
                           TestConanFile("lib", "0.1",
                                         build_requires=["tool/0.1@user/testing"]))
        with self.assertRaisesRegexp(ConanException, "Loop detected: 'tool/0.1@user/testing' "
                                     "requires 'lib/0.1@user/testing'"):
            self.build_graph(TestConanFile("app", "0.1", requires=["lib/0.1@user/testing"]))

    def test_transitive_build_require_recipe_profile(self):
        # app -> lib -(br)-> gtest -(br)-> mingw
        # profile \---(br)-> mingw
        # app -(br)-> mingw
        self._cache_recipe("mingw/0.1@user/testing", TestConanFile("mingw", "0.1"))
        self._cache_recipe("gtest/0.1@user/testing", TestConanFile("gtest", "0.1"))
        self._cache_recipe("lib/0.1@user/testing",
                           TestConanFile("lib", "0.1",
                                         build_requires=["gtest/0.1@user/testing"]))
        profile_build_requires = {"*": [ConanFileReference.loads("mingw/0.1@user/testing")]}
        deps_graph = self.build_graph(TestConanFile("app", "0.1",
                                                    requires=["lib/0.1@user/testing"]),
                                      profile_build_requires=profile_build_requires)

        self.assertEqual(6, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        gtest = lib.dependencies[0].dst
        mingw_gtest = gtest.dependencies[0].dst
        mingw_lib = lib.dependencies[1].dst
        mingw_app = app.dependencies[1].dst

        self._check_node(app, "app/0.1@None/None", deps=[lib], build_deps=[mingw_app], dependents=[],
                         closure=[mingw_app, lib], public_deps=[app, lib])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[], build_deps=[mingw_lib, gtest],
                         dependents=[app], closure=[mingw_lib, gtest], public_deps=[app, lib])
        self._check_node(gtest, "gtest/0.1@user/testing#123", deps=[], build_deps=[mingw_gtest],
                         dependents=[lib], closure=[mingw_gtest], public_deps=[gtest, lib])
        # MinGW leaf nodes
        self._check_node(mingw_gtest, "mingw/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[gtest], closure=[], public_deps=[mingw_gtest, gtest])
        self._check_node(mingw_lib, "mingw/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[lib], closure=[], public_deps=[mingw_lib, gtest, lib])
        self._check_node(mingw_app, "mingw/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[app], closure=[], public_deps=[mingw_app, lib, app])

    def test_conflict_transitive_build_requires(self):
        zlib_ref = "zlib/0.1@user/testing"
        zlib_ref2 = "zlib/0.2@user/testing"
        self._cache_recipe(zlib_ref, TestConanFile("zlib", "0.1"))
        self._cache_recipe(zlib_ref2, TestConanFile("zlib", "0.2"))

        self._cache_recipe("gtest/0.1@user/testing", TestConanFile("gtest", "0.1",
                                                                   requires=[zlib_ref2]))
        self._cache_recipe("lib/0.1@user/testing",
                           TestConanFile("lib", "0.1", requires=[zlib_ref],
                                         build_requires=["gtest/0.1@user/testing"]))

        with self.assertRaisesRegexp(ConanException, "Requirement zlib/0.2@user/testing conflicts"):
            self.build_graph(TestConanFile("app", "0.1", requires=["lib/0.1@user/testing"]))

    def test_not_conflict_transitive_build_requires(self):
        # Same as above, but gtest->(build_require)->zlib2
        zlib_ref = "zlib/0.1@user/testing"
        zlib_ref2 = "zlib/0.2@user/testing"
        self._cache_recipe(zlib_ref, TestConanFile("zlib", "0.1"))
        self._cache_recipe(zlib_ref2, TestConanFile("zlib", "0.2"))

        self._cache_recipe("gtest/0.1@user/testing", TestConanFile("gtest", "0.1",
                                                                   build_requires=[zlib_ref2]))
        self._cache_recipe("lib/0.1@user/testing",
                           TestConanFile("lib", "0.1", requires=[zlib_ref],
                                         build_requires=["gtest/0.1@user/testing"]))

        graph = self.build_graph(TestConanFile("app", "0.1", requires=["lib/0.1@user/testing"]))

        self.assertEqual(5, len(graph.nodes))
        app = graph.root
        lib = app.dependencies[0].dst
        zlib = lib.dependencies[0].dst
        gtest = lib.dependencies[1].dst
        zlib2 = gtest.dependencies[0].dst
        self._check_node(app, "app/0.1@None/None", deps=[lib], build_deps=[], dependents=[],
                         closure=[lib, zlib], public_deps=[app, lib, zlib])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[zlib], build_deps=[gtest],
                         dependents=[app], closure=[gtest, zlib], public_deps=[app, lib, zlib])

        self._check_node(gtest, "gtest/0.1@user/testing#123", deps=[], build_deps=[zlib2],
                         dependents=[lib], closure=[zlib2], public_deps=[gtest, lib, zlib])

    def test_diamond_no_option_conflict_build_requires(self):
        # Same as above, but gtest->(build_require)->zlib2
        zlib_ref = "zlib/0.1@user/testing"
        self._cache_recipe(zlib_ref, TestConanFile("zlib", "0.1",
                                                   options='{"shared": [True, False]}',
                                                   default_options='shared=False'))

        self._cache_recipe("gtest/0.1@user/testing",
                           TestConanFile("gtest", "0.1", requires=[zlib_ref],
                                         default_options='zlib:shared=True'))
        self._cache_recipe("lib/0.1@user/testing",
                           TestConanFile("lib", "0.1", requires=[zlib_ref],
                                         build_requires=["gtest/0.1@user/testing"]))

        graph = self.build_graph(TestConanFile("app", "0.1", requires=["lib/0.1@user/testing"]))

        self.assertEqual(4, len(graph.nodes))
        app = graph.root
        lib = app.dependencies[0].dst
        zlib = lib.dependencies[0].dst
        self.assertFalse(bool(zlib.conanfile.options.shared))
        gtest = lib.dependencies[1].dst
        zlib2 = gtest.dependencies[0].dst
        self.assertIs(zlib, zlib2)
        self._check_node(app, "app/0.1@None/None", deps=[lib], build_deps=[], dependents=[],
                         closure=[lib, zlib], public_deps=[app, lib, zlib])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[zlib], build_deps=[gtest],
                         dependents=[app], closure=[gtest, zlib], public_deps=[app, lib, zlib])

        self._check_node(gtest, "gtest/0.1@user/testing#123", deps=[zlib2], build_deps=[],
                         dependents=[lib], closure=[zlib2], public_deps=[gtest, lib, zlib])

    def test_diamond_option_conflict_build_requires(self):
        # Same as above, but gtest->(build_require)->zlib2
        zlib_ref = "zlib/0.1@user/testing"
        self._cache_recipe(zlib_ref, TestConanFile("zlib", "0.1",
                                                   options='{"shared": [True, False]}',
                                                   default_options='shared=False'))
        configure = """
    def configure(self):
        self.options["zlib"].shared=True
        """
        gtest = str(TestConanFile("gtest", "0.1", requires=[zlib_ref])) + configure
        self._cache_recipe("gtest/0.1@user/testing", gtest)
        self._cache_recipe("lib/0.1@user/testing",
                           TestConanFile("lib", "0.1", requires=[zlib_ref],
                                         build_requires=["gtest/0.1@user/testing"]))

        with self.assertRaisesRegexp(ConanException,
                                     "tried to change zlib/0.1@user/testing option shared to True"):
            self.build_graph(TestConanFile("app", "0.1", requires=["lib/0.1@user/testing"]))

    def test_consecutive_diamonds_build_requires(self):
        # app -> libe0.1 -------------> libd0.1 -> libb0.1 -------------> liba0.1
        #    \-(build-require)-> libf0.1 ->/    \-(build-require)->libc0.1 ->/
        liba_ref = "liba/0.1@user/testing"
        libb_ref = "libb/0.1@user/testing"
        libc_ref = "libc/0.1@user/testing"
        libd_ref = "libd/0.1@user/testing"
        libe_ref = "libe/0.1@user/testing"
        libf_ref = "libf/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1"))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        self._cache_recipe(libc_ref, TestConanFile("libc", "0.1", requires=[liba_ref]))
        self._cache_recipe(libd_ref, TestConanFile("libd", "0.1", requires=[libb_ref],
                                                   build_requires=[libc_ref]))
        self._cache_recipe(libe_ref, TestConanFile("libe", "0.1", requires=[libd_ref]))
        self._cache_recipe(libf_ref, TestConanFile("libf", "0.1", requires=[libd_ref]))
        deps_graph = self.build_graph(TestConanFile("app", "0.1", requires=[libe_ref],
                                                    build_requires=[libf_ref]))

        self.assertEqual(7, len(deps_graph.nodes))
        app = deps_graph.root
        libe = app.dependencies[0].dst
        libf = app.dependencies[1].dst
        libd = libe.dependencies[0].dst
        libb = libd.dependencies[0].dst
        libc = libd.dependencies[1].dst
        liba = libc.dependencies[0].dst

        public_deps = [app, libb, liba, libd, libe]
        self._check_node(app, "app/0.1@None/None", deps=[libe], build_deps=[libf], dependents=[],
                         closure=[libf, libe, libd, libb, liba], public_deps=public_deps)
        self._check_node(libe, "libe/0.1@user/testing#123", deps=[libd], build_deps=[],
                         dependents=[app], closure=[libd, libb, liba],
                         public_deps=public_deps)

        public_deps = [app, libb, liba, libd, libe, libf]
        self._check_node(libf, "libf/0.1@user/testing#123", deps=[libd], build_deps=[],
                         dependents=[app], closure=[libd, libb, liba],
                         public_deps=public_deps)

        public_deps = [app, libb, liba, libd, libe]
        self._check_node(libd, "libd/0.1@user/testing#123", deps=[libb], build_deps=[libc],
                         dependents=[libe, libf], closure=[libc, libb, liba],
                         public_deps=public_deps)
        public_deps = [libd, libb, libc, liba]
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[libd], closure=[liba], public_deps=public_deps)
        public_deps = [app, libb, liba, libd, libe]
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[libd], closure=[liba], public_deps=public_deps)
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb, libc], closure=[], public_deps=public_deps)

    def test_consecutive_diamonds_private(self):
        # app -> libe0.1 -------------> libd0.1 -> libb0.1 -------------> liba0.1
        #    \-(private-req)-> libf0.1 ->/    \-(private-req)->libc0.1 ->/
        liba_ref = "liba/0.1@user/testing"
        libb_ref = "libb/0.1@user/testing"
        libc_ref = "libc/0.1@user/testing"
        libd_ref = "libd/0.1@user/testing"
        libe_ref = "libe/0.1@user/testing"
        libf_ref = "libf/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1"))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        self._cache_recipe(libc_ref, TestConanFile("libc", "0.1", requires=[liba_ref]))
        self._cache_recipe(libd_ref, TestConanFile("libd", "0.1", requires=[libb_ref],
                                                   private_requires=[libc_ref]))
        self._cache_recipe(libe_ref, TestConanFile("libe", "0.1", requires=[libd_ref]))
        self._cache_recipe(libf_ref, TestConanFile("libf", "0.1", requires=[libd_ref]))
        deps_graph = self.build_graph(TestConanFile("app", "0.1", requires=[libe_ref],
                                                    private_requires=[libf_ref]))

        self.assertEqual(7, len(deps_graph.nodes))
        app = deps_graph.root
        libe = app.dependencies[0].dst
        libf = app.dependencies[1].dst
        libd = libe.dependencies[0].dst
        libb = libd.dependencies[0].dst
        libc = libd.dependencies[1].dst
        liba = libc.dependencies[0].dst

        main_public_deps = [app, libb, liba, libd, libe]
        self._check_node(app, "app/0.1@None/None", deps=[libe, libf], build_deps=[], dependents=[],
                         closure=[libe, libf, libd, libb, liba], public_deps=main_public_deps)
        self._check_node(libe, "libe/0.1@user/testing#123", deps=[libd], build_deps=[],
                         dependents=[app], closure=[libd, libb, liba],
                         public_deps=main_public_deps)

        libf_public_deps = [libb, liba, libd, libe, libf]
        self._check_node(libf, "libf/0.1@user/testing#123", deps=[libd], build_deps=[],
                         dependents=[app], closure=[libd, libb, liba],
                         public_deps=libf_public_deps)

        self._check_node(libd, "libd/0.1@user/testing#123", deps=[libb, libc], build_deps=[],
                         dependents=[libe, libf], closure=[libb, libc, liba],
                         public_deps=main_public_deps)

        libc_public_deps = [libb, libc, liba]
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[libd], closure=[liba], public_deps=libc_public_deps)

        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[libd], closure=[liba], public_deps=main_public_deps)
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb, libc], closure=[], public_deps=main_public_deps)

    def test_parallel_diamond_build_requires(self):
        # app --------> libb0.1 ---------> liba0.1
        #    \--------> libc0.1 ----------->/
        #    \-(build_require)-> libd0.1 ->/
        liba_ref = "liba/0.1@user/testing"
        libb_ref = "libb/0.1@user/testing"
        libc_ref = "libc/0.1@user/testing"
        libd_ref = "libd/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1"))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        self._cache_recipe(libc_ref, TestConanFile("libc", "0.1", requires=[liba_ref]))
        self._cache_recipe(libd_ref, TestConanFile("libd", "0.1", requires=[liba_ref]))
        deps_graph = self.build_graph(TestConanFile("app", "0.1",
                                                    requires=[libb_ref, libc_ref],
                                                    build_requires=[libd_ref]))

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        libd = app.dependencies[2].dst
        liba = libb.dependencies[0].dst

        public_deps = [app, libb, libc, liba]
        self._check_node(app, "app/0.1@None/None", deps=[libb, libc], build_deps=[libd],
                         dependents=[], closure=[libd, libb, libc, liba], public_deps=public_deps)
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba], public_deps=public_deps)
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba], public_deps=public_deps)
        public_deps = [app, libd, libb, libc, liba]
        self._check_node(libd, "libd/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba], public_deps=public_deps)
        public_deps = [app, libb, libc, liba]
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb, libc, libd], closure=[], public_deps=public_deps)

    def test_conflict_private(self):
        liba_ref = "liba/0.1@user/testing"
        liba_ref2 = "liba/0.2@user/testing"
        libb_ref = "libb/0.1@user/testing"
        libc_ref = "libc/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1"))
        self._cache_recipe(liba_ref2, TestConanFile("liba", "0.2"))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        self._cache_recipe(libc_ref, TestConanFile("libc", "0.1", requires=[liba_ref2]))
        with self.assertRaisesRegexp(ConanException, "Requirement liba/0.2@user/testing conflicts"):
            self.build_graph(TestConanFile("app", "0.1", private_requires=[libb_ref, libc_ref]))

    def test_loop_private(self):
        # app -> lib -(private)-> tool ->|
        #          \<-----(private)------|
        lib_ref = "lib/0.1@user/testing"
        self._cache_recipe("tool/0.1@user/testing", TestConanFile("tool", "0.1",
                                                                  private_requires=[lib_ref]))
        self._cache_recipe(lib_ref,
                           TestConanFile("lib", "0.1",
                                         private_requires=["tool/0.1@user/testing"]))
        with self.assertRaisesRegexp(ConanException, "Loop detected: 'tool/0.1@user/testing' "
                                     "requires 'lib/0.1@user/testing'"):
            self.build_graph(TestConanFile("app", "0.1", requires=[lib_ref]))

    def test_build_require_private(self):
        # app -> lib -(br)-> tool -(private)-> zlib
        zlib_ref = "zlib/0.1@user/testing"
        self._cache_recipe(zlib_ref, TestConanFile("zlib", "0.1"))
        self._cache_recipe("tool/0.1@user/testing", TestConanFile("tool", "0.1",
                                                                  private_requires=[zlib_ref]))
        self._cache_recipe("lib/0.1@user/testing",
                           TestConanFile("lib", "0.1",
                                         build_requires=["tool/0.1@user/testing"]))
        deps_graph = self.build_graph(TestConanFile("app", "0.1",
                                                    requires=["lib/0.1@user/testing"]))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        tool = lib.dependencies[0].dst
        zlib = tool.dependencies[0].dst

        self._check_node(app, "app/0.1@None/None", deps=[lib], build_deps=[], dependents=[],
                         closure=[lib], public_deps=[app, lib])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[], build_deps=[tool],
                         dependents=[app], closure=[tool], public_deps=[app, lib])

        self._check_node(tool, "tool/0.1@user/testing#123", deps=[zlib], build_deps=[],
                         dependents=[lib], closure=[zlib], public_deps=[tool, lib])

        self._check_node(zlib, "zlib/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[tool], closure=[], public_deps=[zlib])
