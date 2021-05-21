from conans.client.graph.graph import GraphError
from conans.test.assets.genconanfile import GenConanfile
from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest
from conans.test.integration.graph.core.graph_manager_test import _check_transitive


class TestOptions(GraphManagerTest):

    def test_basic(self):
        # app -> libb0.1 (lib shared=True) -> liba0.1 (default static)
        # By default if packages do not specify anything link=True is propagated run=None (unknown)
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requires("liba/0.1").
                              with_default_option("liba:shared", True))
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb], options={"shared": "True"})

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, None),
                                (liba, True, True, False, True)])
        _check_transitive(libb, [(liba, True, True, False, True)])

    def test_app_override(self):
        # app (liba static)-> libb0.1 (liba shared) -> liba0.1 (default static)
        # By default if packages do not specify anything link=True is propagated run=None (unknown)
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requires("liba/0.1").
                              with_default_option("liba:shared", True))
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_requires("libb/0.1").
                                           with_default_option("liba:shared", False))

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb], options={"shared": "False"})

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, None),
                                (liba, True, True, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_diamond_conflict(self):
        # app -> libb0.1 ---------------> liba0.1
        #    \-> libc0.1 (liba shared) -> liba0.1
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requires("liba/0.1").
                              with_default_option("liba:shared", True))

        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])
        deps_graph = self.build_consumer(consumer, install=False)

        assert deps_graph.error == 'Configuration conflict in graph'

        self.assertEqual(4, len(deps_graph.nodes))
