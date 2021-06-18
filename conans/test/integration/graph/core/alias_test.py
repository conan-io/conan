import six

from conans.errors import ConanException
from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest


class AliasTest(GraphManagerTest):

    def test_non_conflicting_alias(self):
        # https://github.com/conan-io/conan/issues/5468
        # libc ----> libb -------------> liba/0.1
        #   \-(build)-> liba/latest -(alias)-/
        self.recipe_cache("liba/0.1")
        self.alias_cache("liba/latest", "liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"], build_requires=["liba/latest"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(liba, "liba/0.1#123", dependents=[libb, app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app], closure=[liba])
        self._check_node(app, "app/0.1", deps=[libb], build_deps=[liba], closure=[libb, liba])

    def test_conflicting_alias(self):
        # https://github.com/conan-io/conan/issues/5468
        # libc ----> libb -------------> liba/0.1
        #   \-(build)-> liba/latest -(alias)-> liba/0.2 (CONFLICT)
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.alias_cache("liba/latest", "liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"], build_requires=["liba/latest"])

        with six.assertRaisesRegex(self, ConanException,
                                   "Conflict in app/0.1:\n"
                                   "    'app/0.1' requires 'liba/0.2' while 'libb/0.1' requires 'liba/0.1'.\n"
                                   "    To fix this conflict you need to override the package 'liba' in your root package."):
            self.build_consumer(consumer)

    def test_conflicting_not_alias(self):
        # https://github.com/conan-io/conan/issues/5468
        # libc ----> libb -------------> liba/0.1
        #   \-(build)-> liba/0.2 (CONFLICT)
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"], build_requires=["liba/0.2"])

        with six.assertRaisesRegex(self, ConanException,
                                   "Conflict in app/0.1:\n"
                                   "    'app/0.1' requires 'liba/0.2' while 'libb/0.1' requires 'liba/0.1'.\n"
                                   "    To fix this conflict you need to override the package 'liba' in your root package."):
            self.build_consumer(consumer)
