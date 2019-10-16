import six
from parameterized import parameterized

from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_INCACHE
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.test.functional.graph.graph_manager_base import GraphManagerTest
from conans.test.utils.tools import GenConanfile


class TransitiveGraphTest(GraphManagerTest):
    def test_basic(self):
        # say/0.1
        deps_graph = self.build_graph(GenConanfile().with_name("Say").with_version("0.1"))
        self.assertEqual(1, len(deps_graph.nodes))
        node = deps_graph.root
        self.assertEqual(node.conanfile.name, "Say")
        self.assertEqual(len(node.dependencies), 0)
        self.assertEqual(len(node.dependants), 0)

    def test_transitive(self):
        # app -> libb0.1
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")
        self._cache_recipe(libb_ref, GenConanfile().with_name("libb").with_version("0.1"))
        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")\
                                                    .with_require(libb_ref))
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
        liba_ref = ConanFileReference.loads("liba/0.1@user/testing")
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")
        self._cache_recipe(liba_ref, GenConanfile().with_name("liba").with_version("0.1"))
        self._cache_recipe(libb_ref, GenConanfile().with_name("libb").with_version("0.1")
                                                   .with_require(liba_ref))
        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(libb_ref))

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        # No Revision??? Because of consumer?
        self._check_node(app, "app/0.1@", deps=[libb], build_deps=[], dependents=[],
                         closure=[libb, liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba])
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb], closure=[])

    def test_diamond(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 ->/
        liba_ref = ConanFileReference.loads("liba/0.1@user/testing")
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")
        libc_ref = ConanFileReference.loads("libc/0.1@user/testing")
        self._cache_recipe(liba_ref, GenConanfile().with_name("liba").with_version("0.1"))
        self._cache_recipe(libb_ref, GenConanfile().with_name("libb").with_version("0.1")
                                                   .with_require(liba_ref))
        self._cache_recipe(libc_ref, GenConanfile().with_name("libc").with_version("0.1")
                                                   .with_require(liba_ref))
        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(libb_ref)
                                                    .with_require(libc_ref))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        # No Revision??? Because of consumer?
        self._check_node(app, "app/0.1@", deps=[libb, libc], build_deps=[], dependents=[],
                         closure=[libb, libc, liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba])
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb, libc], closure=[])

    def test_consecutive_diamonds(self):
        # app -> libe0.1 -> libd0.1 -> libb0.1 -> liba0.1
        #    \-> libf0.1 ->/    \-> libc0.1 ->/
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
                                                   .with_require(libc_ref))
        self._cache_recipe(libe_ref, GenConanfile().with_name("libe").with_version("0.1")
                                                   .with_require(libd_ref))
        self._cache_recipe(libf_ref, GenConanfile().with_name("libf").with_version("0.1")
                                                   .with_require(libd_ref))
        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(libe_ref)
                                                    .with_require(libf_ref))

        self.assertEqual(7, len(deps_graph.nodes))
        app = deps_graph.root
        libe = app.dependencies[0].dst
        libf = app.dependencies[1].dst
        libd = libe.dependencies[0].dst
        libb = libd.dependencies[0].dst
        libc = libd.dependencies[1].dst
        liba = libc.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[libe, libf], build_deps=[], dependents=[],
                         closure=[libe, libf, libd, libb, libc, liba])
        self._check_node(libe, "libe/0.1@user/testing#123", deps=[libd], build_deps=[],
                         dependents=[app], closure=[libd, libb, libc, liba])
        self._check_node(libf, "libf/0.1@user/testing#123", deps=[libd], build_deps=[],
                         dependents=[app], closure=[libd, libb, libc, liba])
        self._check_node(libd, "libd/0.1@user/testing#123", deps=[libb, libc], build_deps=[],
                         dependents=[libe, libf], closure=[libb, libc, liba])
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[libd], closure=[liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[libd], closure=[liba])
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb, libc], closure=[])

    def test_parallel_diamond(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 ->/
        #    \-> libd0.1 ->/
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
                                                    .with_require(libd_ref))

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        libd = app.dependencies[2].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[libb, libc, libd], build_deps=[],
                         dependents=[], closure=[libb, libc, libd, liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba])
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba])
        self._check_node(libd, "libd/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba])
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb, libc, libd], closure=[])

    def test_nested_diamond(self):
        # app --------> libb0.1 -> liba0.1
        #    \--------> libc0.1 ->/
        #     \-> libd0.1 ->/
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
                                                   .with_require(libc_ref))
        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(libb_ref)
                                                    .with_require(libc_ref)
                                                    .with_require(libd_ref))

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        libd = app.dependencies[2].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[libb, libc, libd], build_deps=[],
                         dependents=[], closure=[libb, libd, libc, liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba])
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app, libd], closure=[liba])
        self._check_node(libd, "libd/0.1@user/testing#123", deps=[libc], build_deps=[],
                         dependents=[app], closure=[libc, liba])
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb, libc], closure=[])

    def test_multiple_transitive(self):
        # https://github.com/conanio/conan/issues/4720
        # app -> libb0.1  -> libc0.1 -> libd0.1
        #    \--------------->/          /
        #     \------------------------>/
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")
        libc_ref = ConanFileReference.loads("libc/0.1@user/testing")
        libd_ref = ConanFileReference.loads("libd/0.1@user/testing")
        self._cache_recipe(libd_ref, GenConanfile().with_name("libd").with_version("0.1"))
        self._cache_recipe(libc_ref, GenConanfile().with_name("libc").with_version("0.1")
                                                   .with_require(libd_ref))
        self._cache_recipe(libb_ref, GenConanfile().with_name("libb").with_version("0.1")
                                                   .with_require(libc_ref))
        deps_graph = self.build_graph(GenConanfile().with_name("liba").with_version("0.1")
                                                    .with_require(libd_ref)
                                                    .with_require(libc_ref)
                                                    .with_require(libb_ref))

        self.assertEqual(4, len(deps_graph.nodes))
        liba = deps_graph.root
        libd = liba.dependencies[0].dst
        libc = liba.dependencies[1].dst
        libb = liba.dependencies[2].dst

        self._check_node(libd, "libd/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[liba, libc], closure=[])
        self._check_node(liba, "liba/0.1@", deps=[libd, libc, libb], build_deps=[],
                         dependents=[],
                         closure=[libb, libc, libd])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[libc], build_deps=[],
                         dependents=[liba], closure=[libc, libd])
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[libd], build_deps=[],
                         dependents=[liba, libb], closure=[libd])

    def test_diamond_conflict(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 -> liba0.2
        liba_ref = ConanFileReference.loads("liba/0.1@user/testing")
        liba_ref2 = ConanFileReference.loads("liba/0.2@user/testing")
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")
        libc_ref = ConanFileReference.loads("libc/0.1@user/testing")
        self._cache_recipe(liba_ref, GenConanfile().with_name("liba").with_version("0.1"))
        self._cache_recipe(liba_ref2, GenConanfile().with_name("liba").with_version("0.2"))
        self._cache_recipe(libb_ref, GenConanfile().with_name("libb").with_version("0.1")
                                                   .with_require(liba_ref))
        self._cache_recipe(libc_ref, GenConanfile().with_name("libc").with_version("0.1")
                                                   .with_require(liba_ref2))
        with six.assertRaisesRegex(self, ConanException,
                                   "Requirement liba/0.2@user/testing conflicts"):
            self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                           .with_require(libb_ref)
                                           .with_require(libc_ref))

    def test_loop(self):
        # app -> libc0.1 -> libb0.1 -> liba0.1 ->|
        #             \<-------------------------|
        liba_ref = ConanFileReference.loads("liba/0.1@user/testing")
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")
        libc_ref = ConanFileReference.loads("libc/0.1@user/testing")
        self._cache_recipe(liba_ref, GenConanfile().with_name("liba").with_version("0.1")
                                                   .with_require(libc_ref))
        self._cache_recipe(libb_ref, GenConanfile().with_name("libb").with_version("0.1")
                                                   .with_require(liba_ref))
        self._cache_recipe(libc_ref, GenConanfile().with_name("libc").with_version("0.1")
                                                   .with_require(libb_ref))
        with six.assertRaisesRegex(self, ConanException, "Loop detected: 'liba/0.1@user/testing' "
                                   "requires 'libc/0.1@user/testing'"):
            self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                           .with_require(libc_ref))

    def test_self_loop(self):
        ref1 = ConanFileReference.loads("base/1.0@user/testing")
        self._cache_recipe(ref1, GenConanfile().with_name("base").with_version("0.1"))
        ref = ConanFileReference.loads("base/aaa@user/testing")
        with six.assertRaisesRegex(self, ConanException, "Loop detected: 'base/aaa@user/testing' "
                                   "requires 'base/aaa@user/testing'"):
            self.build_graph(GenConanfile().with_name("base").with_version("aaa")
                                           .with_require(ref1), ref=ref, create_ref=ref)

    @parameterized.expand([("recipe", ), ("profile", )])
    def test_basic_build_require(self, build_require):
        # app -(br)-> tool0.1
        tool_ref = ConanFileReference.loads("tool/0.1@user/testing")
        self._cache_recipe(tool_ref, GenConanfile().with_name("tool")
                                                                  .with_version("0.1"))
        if build_require == "recipe":
            deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                        .with_build_require(tool_ref))
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
                                                  .with_build_require(tool_ref))
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
                                                  .with_build_require(tool_ref))

        with six.assertRaisesRegex(self, ConanException, "Loop detected: 'tool/0.1@user/testing' "
                                   "requires 'lib/0.1@user/testing'"):
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
                                                  .with_build_require(gtest_ref))
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
                                                  .with_build_require(gtest_ref))

        with six.assertRaisesRegex(self, ConanException,
                                   "Requirement zlib/0.2@user/testing conflicts"):
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
                                                    .with_build_require(zlib_ref2))
        self._cache_recipe(lib_ref, GenConanfile().with_name("lib").with_version("0.1")
                                                  .with_require(zlib_ref)
                                                  .with_build_require(gtest_ref))

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
                                                  .with_build_require(gtest_ref))

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
                                                  .with_build_require(gtest_ref))

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
                                                   .with_build_require(libc_ref))
        self._cache_recipe(libe_ref, GenConanfile().with_name("libe").with_version("0.1")
                                                   .with_require(libd_ref))
        self._cache_recipe(libf_ref, GenConanfile().with_name("libf").with_version("0.1")
                                                   .with_require(libd_ref))
        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(libe_ref)
                                                    .with_build_require(libf_ref))

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

    def test_consecutive_diamonds_private(self):
        # app -> libe0.1 -------------> libd0.1 -> libb0.1 -------------> liba0.1
        #    \-(private-req)-> libf0.1 ->/    \-(private-req)->libc0.1 ->/
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
                                                   .with_require(libc_ref, private=True))
        self._cache_recipe(libe_ref, GenConanfile().with_name("libe").with_version("0.1")
                                                   .with_require(libd_ref))
        self._cache_recipe(libf_ref, GenConanfile().with_name("libf").with_version("0.1")
                                                   .with_require(libd_ref))
        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(libe_ref)
                                                    .with_require(libf_ref, private=True))

        self.assertEqual(7, len(deps_graph.nodes))
        app = deps_graph.root
        libe = app.dependencies[0].dst
        libf = app.dependencies[1].dst
        libd = libe.dependencies[0].dst
        libb = libd.dependencies[0].dst
        libc = libd.dependencies[1].dst
        liba = libc.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[libe, libf], build_deps=[], dependents=[],
                         closure=[libe, libf, libd, libb, liba], )
        self._check_node(libe, "libe/0.1@user/testing#123", deps=[libd], build_deps=[],
                         dependents=[app], closure=[libd, libb, liba])

        self._check_node(libf, "libf/0.1@user/testing#123", deps=[libd], build_deps=[],
                         dependents=[app], closure=[libd, libb, liba])
        self._check_node(libd, "libd/0.1@user/testing#123", deps=[libb, libc], build_deps=[],
                         dependents=[libe, libf], closure=[libb, libc, liba])
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
                                                    .with_build_require(libd_ref))

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

    def test_conflict_private(self):
        liba_ref = ConanFileReference.loads("liba/0.1@user/testing")
        liba_ref2 = ConanFileReference.loads("liba/0.2@user/testing")
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")
        libc_ref = ConanFileReference.loads("libc/0.1@user/testing")
        self._cache_recipe(liba_ref, GenConanfile().with_name("liba").with_version("0.1"))
        self._cache_recipe(liba_ref2, GenConanfile().with_name("liba").with_version("0.2"))
        self._cache_recipe(libb_ref, GenConanfile().with_name("libb").with_version("0.1")
                                                   .with_require(liba_ref))
        self._cache_recipe(libc_ref, GenConanfile().with_name("libc").with_version("0.1")
                                                   .with_require(liba_ref2))
        with six.assertRaisesRegex(self, ConanException,
                                   "Requirement liba/0.2@user/testing conflicts"):
            self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                           .with_require(libb_ref, private=True)
                                           .with_require(libc_ref, private=True))

    def test_loop_private(self):
        # app -> lib -(private)-> tool ->|
        #          \<-----(private)------|
        lib_ref = ConanFileReference.loads("lib/0.1@user/testing")
        tool_ref = ConanFileReference.loads("tool/0.1@user/testing")

        self._cache_recipe(tool_ref, GenConanfile().with_name("tool").with_version("0.1")
                                                   .with_require(lib_ref, private=True))
        self._cache_recipe(lib_ref, GenConanfile().with_name("lib").with_version("0.1")
                                                  .with_require(tool_ref, private=True))
        with six.assertRaisesRegex(self, ConanException, "Loop detected: 'tool/0.1@user/testing' "
                                   "requires 'lib/0.1@user/testing'"):
            self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                           .with_require(lib_ref))

    def test_build_require_private(self):
        # app -> lib -(br)-> tool -(private)-> zlib
        zlib_ref = ConanFileReference.loads("zlib/0.1@user/testing")
        tool_ref = ConanFileReference.loads("tool/0.1@user/testing")
        lib_ref = ConanFileReference.loads("lib/0.1@user/testing")

        self._cache_recipe(zlib_ref, GenConanfile().with_name("zlib").with_version("0.1"))
        self._cache_recipe(tool_ref, GenConanfile().with_name("tool").with_version("0.1")
                                                   .with_require(zlib_ref, private=True))
        self._cache_recipe(lib_ref, GenConanfile().with_name("lib").with_version("0.1")
                                                  .with_build_require(tool_ref))
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

    def test_transitive_private_conflict(self):
        # https://github.com/conan-io/conan/issues/4931
        # cheetah -> gazelle -> grass
        #    \--(private)------0.2----/
        grass01_ref = ConanFileReference.loads("grass/0.1@user/testing")
        grass02_ref = ConanFileReference.loads("grass/0.2@user/testing")
        gazelle_ref = ConanFileReference.loads("gazelle/0.1@user/testing")

        self._cache_recipe(grass01_ref, GenConanfile().with_name("grass").with_version("0.1"))
        self._cache_recipe(grass02_ref, GenConanfile().with_name("grass").with_version("0.2"))
        self._cache_recipe(gazelle_ref, GenConanfile().with_name("gazelle").with_version("0.1")
                                                      .with_require(grass01_ref))

        with six.assertRaisesRegex(self, ConanException,
                                   "Requirement grass/0.2@user/testing conflicts"):
            self.build_graph(GenConanfile().with_name("cheetah").with_version("0.1")
                                           .with_require(gazelle_ref)
                                           .with_require(grass02_ref, private=True))

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
                                   "Requirement grass/0.2@user/testing conflicts"):
            self.build_graph(GenConanfile().with_name("cheetah").with_version("0.1")
                                           .with_require(gazelle_ref)
                                           .with_build_require(grass02_ref))

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
                                                    .with_build_require(grass01_ref))

        self.assertEqual(3, len(deps_graph.nodes))
        cheetah = deps_graph.root
        gazelle = cheetah.dependencies[0].dst
        grass = gazelle.dependencies[0].dst
        grass2 = cheetah.dependencies[1].dst

        self._check_node(cheetah, "cheetah/0.1@", deps=[gazelle], build_deps=[grass2],
                         dependents=[], closure=[gazelle, grass])
        self.assertEqual(cheetah.conanfile.deps_cpp_info.libs,
                         ['mylibgazelle0.1lib', 'mylibgrass0.1lib'])

    @parameterized.expand([(True, ), (False, )])
    def test_dont_skip_private(self, private_first):
        liba_ref = ConanFileReference.loads("liba/0.1@user/testing")
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")
        libc_ref = ConanFileReference.loads("libc/0.1@user/testing")

        self._cache_recipe(liba_ref, GenConanfile().with_name("liba").with_version("0.1"))
        self._cache_recipe(libb_ref, GenConanfile().with_name("libb").with_version("0.1")
                                                   .with_require(liba_ref))

        if private_first:
            libc = GenConanfile().with_name("libc").with_version("0.1")\
                                 .with_require(liba_ref, private=True) \
                                 .with_require(libb_ref)
        else:
            libc = GenConanfile().with_name("libc").with_version("0.1")\
                                 .with_require(libb_ref) \
                                 .with_require(liba_ref, private=True)

        self._cache_recipe(libc_ref, libc)
        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(libc_ref))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        if private_first:
            liba = libc.dependencies[0].dst
            libb = libc.dependencies[1].dst
            liba2 = libb.dependencies[0].dst
        else:
            libb = libc.dependencies[0].dst
            liba = libb.dependencies[0].dst
            liba2 = libc.dependencies[1].dst

        self.assertIs(liba, liba2)
        self.assertFalse(liba.private)

        self._check_node(app, "app/0.1@", deps=[libc], build_deps=[], dependents=[],
                         closure=[libc, libb, liba], )
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[libb, liba], build_deps=[],
                         dependents=[app], closure=[libb, liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[libc], closure=[liba])
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libc, libb], closure=[])

    @parameterized.expand([(True, ), (False, )])
    def test_dont_conflict_private(self, private_first):
        liba_ref = ConanFileReference.loads("liba/0.1@user/testing")
        liba_ref2 = ConanFileReference.loads("liba/0.2@user/testing")
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")
        libc_ref = ConanFileReference.loads("libc/0.1@user/testing")

        self._cache_recipe(liba_ref, GenConanfile().with_name("liba").with_version("0.1"))
        self._cache_recipe(liba_ref2, GenConanfile().with_name("liba").with_version("0.2"))
        self._cache_recipe(libb_ref, GenConanfile().with_name("libb").with_version("0.1")
                                                   .with_require(liba_ref, private=True))
        if private_first:
            self._cache_recipe(libc_ref, GenConanfile().with_name("libc").with_version("0.1")
                                                       .with_require(liba_ref2, private=True)
                                                       .with_require(libb_ref))
        else:
            self._cache_recipe(libc_ref, GenConanfile().with_name("libc").with_version("0.1")
                                                       .with_require(libb_ref)
                                                       .with_require(liba_ref2, private=True))

        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(libc_ref))

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        if private_first:
            liba2 = libc.dependencies[0].dst
            libb = libc.dependencies[1].dst
        else:
            libb = libc.dependencies[0].dst
            liba2 = libc.dependencies[1].dst
        liba1 = libb.dependencies[0].dst

        self.assertTrue(liba1.private)
        self.assertTrue(liba2.private)

        self._check_node(app, "app/0.1@", deps=[libc], build_deps=[], dependents=[],
                         closure=[libc, libb])
        closure = [liba2, libb] if private_first else [libb, liba2]
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[libb, liba2], build_deps=[],
                         dependents=[app], closure=closure)
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba1], build_deps=[],
                         dependents=[libc], closure=[liba1])
        self._check_node(liba1, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb], closure=[])
        self._check_node(liba2, "liba/0.2@user/testing#123", deps=[], build_deps=[],
                         dependents=[libc], closure=[])

    def test_consecutive_private(self):
        liba_ref = ConanFileReference.loads("liba/0.1@user/testing")
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")
        libc_ref = ConanFileReference.loads("libc/0.1@user/testing")

        self._cache_recipe(liba_ref, GenConanfile().with_name("liba").with_version("0.1"))
        self._cache_recipe(libb_ref, GenConanfile().with_name("libb").with_version("0.1")
                                                   .with_require(liba_ref, private=True))
        self._cache_recipe(libc_ref, GenConanfile().with_name("libc").with_version("0.1")
                                                   .with_require(libb_ref, private=True))
        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(libc_ref))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self.assertTrue(liba.private)
        self.assertTrue(libb.private)
        self.assertFalse(libc.private)

        self._check_node(app, "app/0.1@", deps=[libc], build_deps=[], dependents=[],
                         closure=[libc])
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[libb], build_deps=[],
                         dependents=[app], closure=[libb])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[libc], closure=[liba])
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb], closure=[])
