from conans.test.assets.genconanfile import GenConanfile
from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest


def _check_transitive(node, transitive_deps):
    values = list(node.transitive_deps.values())
    print(values)
    print(transitive_deps)
    assert len(values) == len(transitive_deps)

    for v1, v2 in zip(values, transitive_deps):
        assert v1.node is v2[0]
        assert v1.require.include is v2[1]
        assert v1.require.link is v2[2]
        assert v1.require.build is v2[3]
        assert v1.require.run is v2[4]


class TestRequiresTransitivityLinear(GraphManagerTest):

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

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, False, True, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_all_static_transitive_headers(self):
        # app -> libb0.1 -> liba0.1
        self.recipe_cache("liba/0.1", option_shared=False)
        libb = GenConanfile().with_requirement("liba/0.1", transitive_headers=True)
        libb.with_shared_option()
        self.recipe_conanfile("libb/0.1", libb)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, True, True, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

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

        # node, include, link, build, run
        # Default for app->liba is that it doesn't link, libb shared will isolate symbols by default
        _check_transitive(app, [(libb, True, True, False, True),
                                (liba, False, False, False, True)])
        _check_transitive(libb, [(liba, True, True, False, True)])

    def test_all_shared_transitive_headers(self):
        # app -> libb0.1 -> liba0.1
        self.recipe_cache("liba/0.1", option_shared=True)
        libb = GenConanfile().with_requirement("liba/0.1", transitive_headers=True)
        libb.with_shared_option(True)
        self.recipe_conanfile("libb/0.1", libb)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        # Default for app->liba is that it doesn't link, libb shared will isolate symbols by default
        _check_transitive(app, [(libb, True, True, False, True),
                                (liba, True, False, False, True)])
        _check_transitive(libb, [(liba, True, True, False, True)])

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

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, True),
                                (liba, False, False, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_middle_shared_up_static_transitive_headers(self):
        # app -> libb0.1 -> liba0.1
        self.recipe_cache("liba/0.1", option_shared=False)
        libb = GenConanfile().with_requirement("liba/0.1", transitive_headers=True)
        libb.with_shared_option(True)
        self.recipe_conanfile("libb/0.1", libb)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, True),
                                (liba, True, False, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

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

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, False, True, False, True)])
        _check_transitive(libb, [(liba, True, True, False, True)])

    def test_middle_static_up_shared_transitive_headers(self):
        # app -> libb0.1 (static) -> liba0.1 (shared)
        self.recipe_cache("liba/0.1", option_shared=True)
        libb = GenConanfile().with_requirement("liba/0.1", transitive_headers=True)
        libb.with_shared_option(False)
        self.recipe_conanfile("libb/0.1", libb)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, True, True, False, True)])
        _check_transitive(libb, [(liba, True, True, False, True)])


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
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, True),
                                (libc, True, True, False, True),
                                (liba, False, False, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])
        _check_transitive(libc, [(liba, True, True, False, False)])

    def test_shared_static_private(self):
        # app -> libb0.1 (shared) -(private)-> liba0.1 (static)
        #    \-> libc0.1 (shared) -> liba0.2 (static)
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_cache("liba/0.2", option_shared=False)
        libb = GenConanfile().with_requirement("liba/0.1", public=False)
        libb.with_shared_option(True)
        self.recipe_conanfile("libb/0.1", libb)
        self.recipe_cache("libc/0.1", ["liba/0.2"], option_shared=True)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba1 = libb.dependencies[0].dst
        liba2 = libc.dependencies[0].dst

        assert liba1 is not liba2

        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba1], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba2], dependents=[app])
        self._check_node(liba1, "liba/0.1#123", dependents=[libb])
        self._check_node(liba2, "liba/0.2#123", dependents=[libc])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, True),
                                (libc, True, True, False, True),
                                (liba2, False, False, False, False)])
        _check_transitive(libb, [(liba1, True, True, False, False)])
        _check_transitive(libc, [(liba2, True, True, False, False)])
