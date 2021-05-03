from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_INCACHE, RECIPE_MISSING
from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest
from conans.test.utils.tools import GenConanfile


class TestRequiresTransitivity(GraphManagerTest):

    def test_all_static(self):
        # app -> libb0.1 -> liba0.1
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_cache("libb/0.1", ["liba/0.1"], option_shared=False)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        values = list(app.transitive_deps.values())
        assert len(values) == 2
        dep_libb = values[0]
        assert dep_libb.node == libb
        assert dep_libb.require.link is True
        assert dep_libb.require.build is False
        assert dep_libb.require.run is False
        assert dep_libb.require.headers == "private"

        dep_liba = values[1]
        assert dep_liba.node == liba
        assert dep_liba.require.link is True
        assert dep_liba.require.build is False
        assert dep_liba.require.run is False
        assert dep_liba.require.headers is False

        values = list(libb.transitive_deps.values())
        assert len(values) == 1

        dep_liba = values[0]
        assert dep_liba.node == liba
        assert dep_liba.require.link is True
        assert dep_liba.require.build is False
        assert dep_liba.require.run is False
        assert dep_liba.require.headers == "private"

    def test_all_shared(self):
        # app -> libb0.1 -> liba0.1
        self.recipe_cache("liba/0.1", option_shared=True)
        self.recipe_cache("libb/0.1", ["liba/0.1"], option_shared=True)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        values = list(app.transitive_deps.values())
        assert len(values) == 2
        dep_libb = values[0]
        assert dep_libb.node == libb
        assert dep_libb.require.link is True
        assert dep_libb.require.build is False
        assert dep_libb.require.run is True

        dep_liba = values[1]
        assert dep_liba.node == liba
        assert dep_liba.require.link is False
        assert dep_liba.require.build is False
        assert dep_liba.require.run is True

        values = list(libb.transitive_deps.values())
        assert len(values) == 1

        dep_liba = values[0]
        assert dep_liba.node == liba
        assert dep_liba.require.link is True
        assert dep_liba.require.build is False
        assert dep_liba.require.run is True

    def test_middle_shared_up_static(self):
        # app -> libb0.1 -> liba0.1
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_cache("libb/0.1", ["liba/0.1"], option_shared=True)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        values = list(app.transitive_deps.values())
        assert len(values) == 1
        dep_libb = values[0]
        assert dep_libb.node == libb
        assert dep_libb.require.link is True
        assert dep_libb.require.build is False
        assert dep_libb.require.run is True

        values = list(libb.transitive_deps.values())
        assert len(values) == 1

        dep_liba = values[0]
        assert dep_liba.node == liba
        assert dep_liba.require.link is True
        assert dep_liba.require.build is False
        assert dep_liba.require.run is False

    def test_middle_static_up_shared(self):
        # app -> libb0.1 -> liba0.1
        self.recipe_cache("liba/0.1", option_shared=True)
        self.recipe_cache("libb/0.1", ["liba/0.1"], option_shared=False)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        values = list(app.transitive_deps.values())
        assert len(values) == 2
        dep_libb = values[0]
        assert dep_libb.node == libb
        assert dep_libb.require.link is True
        assert dep_libb.require.build is False
        assert dep_libb.require.run is False

        dep_liba = values[1]
        assert dep_liba.node == liba
        assert dep_liba.require.link is True
        assert dep_liba.require.build is False
        assert dep_liba.require.run is True

        values = list(libb.transitive_deps.values())
        assert len(values) == 1

        dep_liba = values[0]
        assert dep_liba.node == liba
        assert dep_liba.require.link is True
        assert dep_liba.require.build is False
        assert dep_liba.require.run is True
