from conan.test.assets.genconanfile import GenConanfile
from test.integration.graph.core.graph_manager_base import GraphManagerTest
from test.integration.graph.core.graph_manager_test import _check_transitive


class TestOptions(GraphManagerTest):

    def test_basic(self):
        # app -> libb0.1 (lib shared=True) -> liba0.1 (default static)
        # By default if packages do not specify anything link=True is propagated run=None (unknown)
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requires("liba/0.1").
                              with_default_option("liba/*:shared", True))
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
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, True, True, False, True)])
        _check_transitive(libb, [(liba, True, True, False, True)])

    def test_app_override(self):
        # app (liba static)-> libb0.1 (liba shared) -> liba0.1 (default static)
        # By default if packages do not specify anything link=True is propagated run=None (unknown)
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requires("liba/0.1").
                              with_default_option("liba/*:shared", True))
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_requires("libb/0.1").
                                           with_default_option("liba/*:shared", False))

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb], options={"shared": "False"})

        # node, include, link, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, True, True, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_diamond_no_conflict(self):
        # app -> libb0.1 ---------------> liba0.1
        #    \-> libc0.1 (liba shared) -> liba0.1
        # Just the first expanded one will prevail
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requires("liba/0.1").
                              with_default_option("liba*:shared", True))

        # If we expand first the "libb", it will expand to "liba" as static (shared=False)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])
        deps_graph = self.build_consumer(consumer)
        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst
        liba2 = libc.dependencies[0].dst
        assert liba is liba2
        self._check_node(app, "app/0.1", deps=[libc, libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc], options={"shared": "False"})

        # Changing the order, will make "liba" shared=True
        consumer = self.recipe_consumer("app/0.1", ["libc/0.1", "libb/0.1"])
        deps_graph = self.build_consumer(consumer)
        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = app.dependencies[1].dst
        liba = libb.dependencies[0].dst
        liba2 = libc.dependencies[0].dst
        assert liba is liba2
        self._check_node(app, "app/0.1", deps=[libc, libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc], options={"shared": "True"})

    def test_diamond_downstream_priority(self):
        # app(liba:shared) -> libb0.1 ---------------> liba0.1
        #    \--------------> libc0.1 (liba shared) -> liba0.1
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requires("liba/0.1").
                              with_default_option("liba*:shared", True))

        for shared in True, False:
            consumer = self.consumer_conanfile(GenConanfile("app", "0.1")
                                               .with_requires("libb/0.1", "libc/0.1")
                                               .with_default_option("liba*:shared", shared))
            deps_graph = self.build_consumer(consumer)

            self.assertEqual(4, len(deps_graph.nodes))
            app = deps_graph.root
            libb = app.dependencies[0].dst
            libc = app.dependencies[1].dst
            liba = libb.dependencies[0].dst
            liba2 = libc.dependencies[0].dst
            assert liba is liba2
            self._check_node(app, "app/0.1", deps=[libc, libb])
            self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
            self._check_node(liba, "liba/0.1#123", dependents=[libb, libc],
                             options={"shared": str(shared)})

            # order doesn't matter
            consumer = self.consumer_conanfile(GenConanfile("app", "0.1")
                                               .with_requires("libc/0.1", "libb/0.1")
                                               .with_default_option("liba*:shared", shared))
            deps_graph = self.build_consumer(consumer)

            self.assertEqual(4, len(deps_graph.nodes))
            app = deps_graph.root
            libc = app.dependencies[0].dst
            libb = app.dependencies[1].dst
            liba = libb.dependencies[0].dst
            liba2 = libc.dependencies[0].dst
            assert liba is liba2
            self._check_node(app, "app/0.1", deps=[libc, libb])
            self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
            self._check_node(liba, "liba/0.1#123", dependents=[libb, libc],
                             options={"shared": str(shared)})


class TestBuildRequireOptions(GraphManagerTest):
    def test_protobuf_different_options_profile(self):
        # app -> lib ------> protobuf -> zlib (shared)
        #          \--(br)-> protobuf -> zlib (static)
        self._cache_recipe("zlib/0.1", GenConanfile().with_shared_option(True))
        self._cache_recipe("protobuf/0.1", GenConanfile().with_require("zlib/0.1"))
        self._cache_recipe("lib/0.1", GenConanfile().with_requires("protobuf/0.1").
                           with_tool_requires("protobuf/0.1"))
        deps_graph = self.build_graph(GenConanfile("app", "0.1").with_require("lib/0.1"),
                                      options_build={"zlib*:shared": False})

        self.assertEqual(6, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        protobuf_host = lib.dependencies[0].dst
        protobuf_build = lib.dependencies[1].dst
        zlib_shared = protobuf_host.dependencies[0].dst
        zlib_static = protobuf_build.dependencies[0].dst

        self._check_node(app, "app/0.1@", deps=[lib], dependents=[])
        self._check_node(lib, "lib/0.1#123", deps=[protobuf_host, protobuf_build], dependents=[app])
        self._check_node(protobuf_host, "protobuf/0.1#123", deps=[zlib_shared], dependents=[lib])
        self._check_node(protobuf_build, "protobuf/0.1#123", deps=[zlib_static], dependents=[lib])
        self._check_node(zlib_shared, "zlib/0.1#123", deps=[], dependents=[protobuf_host])
        self._check_node(zlib_static, "zlib/0.1#123", deps=[], dependents=[protobuf_build])
        assert not zlib_static.conanfile.options.shared
        assert zlib_shared.conanfile.options.shared

        # node, include, link, build, run
        _check_transitive(app, [(lib, True, True, False, False),
                                (protobuf_host, True, True, False, False),
                                (zlib_shared, True, True, False, True)])
        _check_transitive(lib, [(protobuf_host, True, True, False, False),
                                (zlib_shared, True, True, False, True),
                                (protobuf_build, False, False, True, True)])
