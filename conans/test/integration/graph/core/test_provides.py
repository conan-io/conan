from conans.client.graph.graph import GraphError
from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest
from conans.test.utils.tools import GenConanfile


class ProvidesTest(GraphManagerTest):

    def test_diamond_conflict(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 -> libd0.2 (provides liba)
        self.recipe_cache("liba/0.1")
        self.recipe_conanfile("libd/0.2", GenConanfile().with_provides("liba"))
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["libd/0.2"])

        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])
        deps_graph = self.build_consumer(consumer, install=False)

        assert deps_graph.error is True

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba1 = libb.dependencies[0].dst
        libd2 = libc.dependencies[0].dst
        self._check_node(app, "app/0.1", deps=[libb, libc])
        assert app.conflict == (GraphError.PROVIDE_CONFLICT, [liba1, libd2])
        self._check_node(libb, "libb/0.1#123", deps=[liba1], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libd2], dependents=[app])

        self._check_node(liba1, "liba/0.1#123", dependents=[libb])
        # TODO: Conflicted without revision
        self._check_node(libd2, "libd/0.2#123", dependents=[libc])

    def test_loop(self):
        # app -> libc0.1 -> libb0.1 -> liba0.1 ->|
        #             \<------(provides)---------|
        self.recipe_conanfile("liba/0.1", GenConanfile().with_provides("libc"))
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["libb/0.1"])

        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        deps_graph = self.build_consumer(consumer, install=False)
        assert deps_graph.error is True

        self.assertEqual(4, len(deps_graph.nodes))

        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        assert app.conflict == (GraphError.PROVIDE_CONFLICT, [libc, liba])
