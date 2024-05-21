from conan.test.assets.genconanfile import GenConanfile
from test.integration.graph.core.graph_manager_base import GraphManagerTest
from test.integration.graph.core.graph_manager_test import _check_transitive
from conan.test.utils.tools import TestClient


class TestAlias(GraphManagerTest):

    def test_basic(self):
        # app -> liba/latest -(alias)-> liba/0.1
        self.recipe_cache("liba/0.1")
        self.alias_cache("liba/latest", "liba/0.1")

        consumer = self.recipe_consumer("app/0.1", ["liba/(latest)"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        liba = app.dependencies[0].dst

        self._check_node(liba, "liba/0.1#123", dependents=[app])
        self._check_node(app, "app/0.1", deps=[liba])

    def test_alias_diamond(self):
        # app -> ----------------------------------> liba/0.1
        #   \ -> libb/0.1 -> liba/latest -(alias) ----->/
        self.recipe_cache("liba/0.1")
        self.alias_cache("liba/latest", "liba/0.1")
        self.recipe_cache("libb/0.1", requires=["liba/(latest)"])
        consumer = self.recipe_consumer("app/0.1", ["liba/0.1", "libb/0.1"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        liba = app.dependencies[0].dst
        libb = app.dependencies[1].dst

        self._check_node(liba, "liba/0.1#123", dependents=[app, libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(app, "app/0.1", deps=[liba, libb])

        # node, include, link, build, run
        # It seems they are in link order
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, True, True, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_two_alias_diamond(self):
        # https://github.com/conan-io/conan/issues/3353
        # app -> liba/latest -(alias) --------------------------------------> liba/0.1
        #   \ -> libb/latest -(alias) -> libb/0.1 -> liba/latest -(alias) ----->/

        self.recipe_cache("liba/0.1")
        self.alias_cache("liba/latest", "liba/0.1")
        self.recipe_cache("libb/0.1", requires=["liba/(latest)"])
        self.alias_cache("libb/latest", "libb/0.1")

        consumer = self.recipe_consumer("app/0.1", ["liba/(latest)", "libb/(latest)"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        liba = app.dependencies[0].dst
        libb = app.dependencies[1].dst

        self._check_node(liba, "liba/0.1#123", dependents=[app, libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(app, "app/0.1", deps=[liba, libb])

        # node, include, link, build, run
        # Seems reverse order
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, True, True, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_full_two_branches_diamond(self):
        # https://github.com/conan-io/conan/issues/3353
        # app -> libb/latest -(alias) -> libb/0.1 -> liba/latest -(alias) ----> liba/0.1
        #   \ -> libc/latest -(alias) -> libc/0.1 -> liba/latest -(alias) ----->/

        self.recipe_cache("liba/0.1")
        self.alias_cache("liba/latest", "liba/0.1")
        self.recipe_cache("libb/0.1", requires=["liba/(latest)"])
        self.recipe_cache("libc/0.1", requires=["liba/(latest)"])
        self.alias_cache("libb/latest", "libb/0.1")
        self.alias_cache("libc/latest", "libc/0.1")

        consumer = self.recipe_consumer("app/0.1", ["libb/(latest)", "libc/(latest)"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app])
        self._check_node(app, "app/0.1", deps=[libb, libc])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (libc, True, True, False, False),
                                (liba, True, True, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_alias_bug(self):
        # https://github.com/conan-io/conan/issues/2252
        # app -> libb/0.1 -> liba/latest -(alias)->liba/0.1
        #   \ -> libc/0.1 ----/
        self.recipe_cache("liba/0.1")
        self.alias_cache("liba/latest", "liba/0.1")
        self.recipe_cache("libb/0.1", requires=["liba/(latest)"])
        self.recipe_cache("libc/0.1", requires=["liba/(latest)"])

        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app])
        self._check_node(app, "app/0.1", deps=[libb, libc])

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (libc, True, True, False, False),
                                (liba, True, True, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_alias_tansitive(self):
        # app -> liba/giga -(alias)->-> liba/mega -(alias)-> liba/latest -(alias)->liba/0.1

        self.recipe_cache("liba/0.1")
        self.alias_cache("liba/latest", "liba/0.1")
        self.alias_cache("liba/mega", "liba/(latest)")
        self.alias_cache("liba/giga", "liba/(mega)")

        consumer = self.recipe_consumer("app/0.1", ["liba/(giga)"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        liba = app.dependencies[0].dst

        self._check_node(liba, "liba/0.1#123", dependents=[app])
        self._check_node(app, "app/0.1", deps=[liba])

        # node, include, link, build, run
        _check_transitive(app, [(liba, True, True, False, False)])


class AliasBuildRequiresTest(GraphManagerTest):

    def test_non_conflicting_alias(self):
        # https://github.com/conan-io/conan/issues/5468
        # libc ----> libb -------------------> liba/0.1
        #   \-(build)-> liba/latest -(alias)-> liba/0.2
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.alias_cache("liba/latest", "liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"], build_requires=["liba/(latest)"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba_build = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        self._check_node(liba, "liba/0.1#123", dependents=[libb])
        self._check_node(liba_build, "liba/0.2#123", dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(app, "app/0.1", deps=[libb, liba_build])


def test_mixing_aliases_and_fix_versions():
    # cd/1.0 -----------------------------> cb/latest -(alias)-> cb/1.0 -> ca/1.0
    #   \-----> cc/latest -(alias)-> cc/1.0 ->/                             /
    #                                    \------ ca/latest -(alias)------->/
    client = TestClient(light=True)

    client.save({"conanfile.py": GenConanfile("ca", "1.0")})
    client.run("create . ")
    client.alias("ca/latest@",  "ca/1.0@")

    client.save({"conanfile.py": GenConanfile("cb", "1.0").with_requirement("ca/1.0@")})
    client.run("create . --name=cb --version=1.0")
    client.alias("cb/latest@",  "cb/1.0@")

    client.save({"conanfile.py": GenConanfile("cc", "1.0")
                .with_requirement("cb/(latest)")
                .with_requirement("ca/(latest)")})
    client.run("create . ")
    client.alias("cc/latest@",  "cc/1.0@")

    client.save({"conanfile.py": GenConanfile("cd", "1.0")
                .with_requirement("cb/(latest)")
                .with_requirement("cc/(latest)")})
    client.run("create . ")
