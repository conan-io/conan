from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_INCACHE
from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest
from conans.test.utils.tools import GenConanfile


class TestVersionRanges(GraphManagerTest):

    def test_transitive(self):
        # app -> libb[>0.1]
        self.recipe_cache("libb/0.1")
        self.recipe_cache("libb/0.2")
        consumer = self.recipe_consumer("app/0.1", ["libb/[>=0.0]"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        self.assertEqual(app.conanfile.name, "app")
        self.assertEqual(app.recipe, RECIPE_CONSUMER)
        self.assertEqual(len(app.dependencies), 1)
        self.assertEqual(len(app.dependants), 0)

        libb = app.dependencies[0].dst
        self.assertEqual(libb.conanfile.name, "libb")
        self.assertEqual(len(libb.dependencies), 0)
        self.assertEqual(len(libb.dependants), 1)
        self.assertEqual(libb.inverse_neighbors(), [app])
        self.assertEqual(libb.recipe, RECIPE_INCACHE)
        assert libb.package_id == "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
