from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest


class TestRequiresTransitivityLinear(GraphManagerTest):

    @staticmethod
    def _check_transitive(node, transitive_deps):
        values = list(node.transitive_deps.values())
        assert len(values) == len(transitive_deps)

        for v1, v2 in zip(values, transitive_deps):
            assert v1.node is v2[0]
            assert v1.require.link is v2[1]
            assert v1.require.build is v2[2]
            assert v1.require.run is v2[3]

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

        # node, link, build, run
        self._check_transitive(app, [(libb, True, False, False),
                                     (liba, True, False, False)])
        self._check_transitive(libb, [(liba, True, False, False)])

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

        # node, link, build, run
        # Default for app->liba is that it doesn't link, libb shared will isolate symbols by default
        self._check_transitive(app, [(libb, True, False, True),
                                     (liba, False, False, True)])
        self._check_transitive(libb, [(liba, True, False, True)])

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

        # node, link, build, run
        self._check_transitive(app, [(libb, True, False, True),
                                     (liba, False, False, False)])
        self._check_transitive(libb, [(liba, True, False, False)])

    def test_middle_static_up_shared(self):
        # app -> libb0.1 (static) -> liba0.1 (shared)
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

        # node, link, build, run
        self._check_transitive(app, [(libb, True, False, False),
                                     (liba, True, False, True)])
        self._check_transitive(libb, [(liba, True, False, True)])


class TestRequiresTransitivityDiamond(GraphManagerTest):

    def test_shared_static(self):
        # app -> libb0.1 (shared) -> liba0.1 (static)
        #    \-> libc0.1 (shared) ->/
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_cache("libb/0.1", ["liba/0.1"], option_shared=True)
        self.recipe_cache("libc/0.1", ["liba/0.1"], option_shared=True)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst
        liba1 = libc.dependencies[0].dst

        assert liba is liba1

        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

        values = list(app.transitive_deps.values())
        assert len(values) == 3
        dep_libb = values[0]
        assert dep_libb.node == libb
        assert dep_libb.require.link is True
        assert dep_libb.require.build is False
        assert dep_libb.require.run is True

        dep_libc = values[1]
        assert dep_libc.node == libc
        assert dep_libc.require.link is True
        assert dep_libc.require.build is False
        assert dep_libc.require.run is True

        dep_liba = values[2]
        assert dep_liba.node == liba
        assert dep_liba.require.link is False
        assert dep_liba.require.build is False
        assert dep_liba.require.run is False

        values = list(libb.transitive_deps.values())
        assert len(values) == 1

        dep_liba = values[0]
        assert dep_liba.node == liba
        assert dep_liba.require.link is True
        assert dep_liba.require.build is False
        assert dep_liba.require.run is False
