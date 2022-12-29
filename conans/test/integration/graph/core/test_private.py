import six
from parameterized import parameterized

from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest
from conans.test.utils.tools import GenConanfile


class PrivateGraphTest(GraphManagerTest):

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
                                   "Conflict in libc/0.1@user/testing:\n"
                                   "    'libc/0.1@user/testing' requires 'liba/0.2@user/testing' "
                                   "while 'libb/0.1@user/testing' requires 'liba/0.1@user/testing'."
                                   "\n    To fix this conflict you need to override the package "
                                   "'liba' in your root package."):
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
        with six.assertRaisesRegex(self, ConanException, "Loop detected in context host:"
                                                         " 'tool/0.1@user/testing'"
                                                         " requires 'lib/0.1@user/testing'"):
            self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                           .with_require(lib_ref))

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
                                   "Conflict in cheetah/0.1:\n"
            "    'cheetah/0.1' requires 'grass/0.2@user/testing' while 'gazelle/0.1@user/testing'"
            " requires 'grass/0.1@user/testing'.\n"
            "    To fix this conflict you need to override the package 'grass' in your root"
            " package."):
            self.build_graph(GenConanfile().with_name("cheetah").with_version("0.1")
                                           .with_require(gazelle_ref)
                                           .with_require(grass02_ref, private=True))

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

        self._check_node(app, "app/0.1@", deps=[libc], build_deps=[], dependents=[],
                         closure=[libc])
        self._check_node(libc, "libc/0.1@user/testing#123", deps=[libb], build_deps=[],
                         dependents=[app], closure=[libb])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[libc], closure=[liba])
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb], closure=[])
