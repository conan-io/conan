import six

from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_INCACHE
from conans.errors import ConanException
from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest
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
        self.recipe_cache("libb/0.1")
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

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
        self.assertEqual(list(libb.ancestors), [app])
        self.assertEqual(libb.recipe, RECIPE_INCACHE)

        self.assertEqual(list(app.public_closure), [libb])
        self.assertEqual(list(libb.public_closure), [])
        self.assertEqual(list(app.public_deps), [app, libb])
        self.assertEqual(list(libb.public_deps), list(app.public_deps))

    def test_transitive_two_levels(self):
        # app -> libb0.1 -> liba0.1
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb], closure=[libb, liba])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app], closure=[liba])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

    def test_diamond(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        # No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libb, libc], closure=[libb, libc, liba])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app], closure=[liba])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app], closure=[liba])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

    def test_consecutive_diamonds(self):
        # app -> libe0.1 -> libd0.1 -> libb0.1 -> liba0.1
        #    \-> libf0.1 ->/    \-> libc0.1 ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        self.recipe_cache("libd/0.1", ["libb/0.1", "libc/0.1"])
        self.recipe_cache("libe/0.1", ["libd/0.1"])
        self.recipe_cache("libf/0.1", ["libd/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libe/0.1", "libf/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(7, len(deps_graph.nodes))
        app = deps_graph.root
        libe = app.dependencies[0].dst
        libf = app.dependencies[1].dst
        libd = libe.dependencies[0].dst
        libb = libd.dependencies[0].dst
        libc = libd.dependencies[1].dst
        liba = libc.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libe, libf],
                         closure=[libe, libf, libd, libb, libc, liba])
        self._check_node(libe, "libe/0.1#123", deps=[libd], dependents=[app],
                         closure=[libd, libb, libc, liba])
        self._check_node(libf, "libf/0.1#123", deps=[libd], dependents=[app],
                         closure=[libd, libb, libc, liba])
        self._check_node(libd, "libd/0.1#123", deps=[libb, libc], dependents=[libe, libf],
                         closure=[libb, libc, liba])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[libd], closure=[liba])
        self._check_node(libb, "libb/0.1#123", deps=[liba],  dependents=[libd], closure=[liba])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

    def test_parallel_diamond(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 ->/
        #    \-> libd0.1 ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        self.recipe_cache("libd/0.1", ["liba/0.1"])

        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1", "libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        libd = app.dependencies[2].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb, libc, libd], closure=[libb, libc, libd, liba])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app], closure=[liba])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app], closure=[liba])
        self._check_node(libd, "libd/0.1#123", deps=[liba], dependents=[app], closure=[liba])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc, libd])

    def test_nested_diamond(self):
        # app --------> libb0.1 -> liba0.1
        #    \--------> libc0.1 ->/
        #     \-> libd0.1 ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        self.recipe_cache("libd/0.1", ["libc/0.1"])

        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1", "libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        libd = app.dependencies[2].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb, libc, libd], closure=[libb, libd, libc, liba])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app], closure=[liba])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app, libd], closure=[liba])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app], closure=[libc, liba])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

    def test_multiple_transitive(self):
        # https://github.com/conanio/conan/issues/4720
        # app -> libb0.1  -> libc0.1 -> libd0.1
        #    \--------------->/          /
        #     \------------------------>/
        self.recipe_cache("libd/0.1")
        self.recipe_cache("libc/0.1", ["libd/0.1"])
        self.recipe_cache("libb/0.1", ["libc/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1", "libc/0.1", "libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        libb = app.dependencies[2].dst

        self._check_node(app, "app/0.1", deps=[libd, libc, libb], closure=[libb, libc, libd])
        self._check_node(libd, "libd/0.1#123", dependents=[app, libc])
        self._check_node(libb, "libb/0.1#123", deps=[libc], dependents=[app], closure=[libc, libd])
        self._check_node(libc, "libc/0.1#123", deps=[libd], dependents=[app, libb], closure=[libd])

    def test_diamond_conflict(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 -> liba0.2
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.2"])

        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])

        with six.assertRaisesRegex(self, ConanException, "Conflict in libc/0.1:\n"
            "    'libc/0.1' requires 'liba/0.2' while 'libb/0.1' requires 'liba/0.1'.\n"
            "    To fix this conflict you need to override the package 'liba' in your root "
            "package."):
            self.build_consumer(consumer)

    def test_loop(self):
        # app -> libc0.1 -> libb0.1 -> liba0.1 ->|
        #             \<-------------------------|
        self.recipe_cache("liba/0.1", ["libc/0.1"])
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["libb/0.1"])

        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        with six.assertRaisesRegex(self, ConanException,
                                   "Loop detected in context host: 'liba/0.1' requires 'libc/0.1'"):
            self.build_consumer(consumer)

    def test_self_loop(self):
        self.recipe_cache("liba/0.1")
        consumer = self.recipe_consumer("liba/0.2", ["liba/0.1"])
        with six.assertRaisesRegex(self, ConanException,
                                   "Loop detected in context host: 'liba/0.2' requires 'liba/0.1'"):
            self.build_consumer(consumer)
