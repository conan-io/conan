import pytest
from parameterized import parameterized

from conans.client.graph.graph_error import GraphMissingError, GraphLoopError, GraphConflictError
from conans.errors import ConanException
from test.integration.graph.core.graph_manager_base import GraphManagerTest
from conan.test.utils.tools import GenConanfile


def _check_transitive(node, transitive_deps):
    values = list(node.transitive_deps.values())

    if len(values) != len(transitive_deps):
        values = [r.require.ref for r in values]
        raise Exception("{}: Number of deps don't match \n{}!=\n{}".format(node, values,
                                                                           transitive_deps))

    for v1, v2 in zip(values, transitive_deps):
        if v1.node is not v2[0]:
            raise Exception(f"{v1.node}!={v2[0]}")
        if v1.require.headers is not v2[1]:
            raise Exception(f"{v1.node}!={v2[0]} headers")
        if v1.require.libs is not v2[2]:
            raise Exception(f"{v1.node}!={v2[0]} libs")
        if v1.require.build is not v2[3]:
            raise Exception(f"{v1.node}!={v2[0]} build")
        if v1.require.run is not v2[4]:
            raise Exception(f"{v1.node}!={v2[0]} run")
        if len(v2) > 5:
            assert v1.require.package_id_mode is v2[5]


class TestLinear(GraphManagerTest):
    def test_basic(self):
        deps_graph = self.build_graph(GenConanfile("app", "0.1"))
        self.assertEqual(1, len(deps_graph.nodes))
        node = deps_graph.root
        self._check_node(node, "app/0.1")

    def test_dependency(self):
        # app -> libb0.1
        self.recipe_cache("libb/0.1")
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[], dependents=[app])

    def test_dependency_missing(self):
        # app -> libb0.1 (non existing)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])
        deps_graph = self.build_consumer(consumer, install=False)

        # TODO: Better error handling
        assert type(deps_graph.error) == GraphMissingError

        self.assertEqual(1, len(deps_graph.nodes))
        app = deps_graph.root
        self._check_node(app, "app/0.1", deps=[])

    def test_transitive(self):
        # app -> libb0.1 -> liba0.1
        # By default if packages do not specify anything link=True is propagated run=None (unknown)
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, True, True, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_transitive_propagate_link(self):
        # app -> libb0.1 -> liba0.1
        # transitive_link=False will avoid propagating linkage requirement
        self.recipe_cache("liba/0.1")
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1",
                                                                          transitive_libs=False))
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, True, False, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_transitive_all_static(self):
        # app -> libb0.1 (static) -> liba0.1 (static)
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_cache("libb/0.1", ["liba/0.1"], option_shared=False)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        for r, t in libb.transitive_deps.items():
            assert r.package_id_mode == "minor_mode"

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, False, True, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_transitive_all_static_transitive_headers(self):
        # app -> libb0.1 (static) -> liba0.1 (static)
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

        # node, headers, lib, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, True, True, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_transitive_all_shared(self):
        # app -> libb0.1 (shared)  -> liba0.1 (shared)
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

        # node, headers, lib, build, run
        # Default for app->liba is that it doesn't link, libb shared will isolate symbols by default
        _check_transitive(app, [(libb, True, True, False, True),
                                (liba, False, False, False, True)])
        _check_transitive(libb, [(liba, True, True, False, True)])

    def test_transitive_all_shared_transitive_headers_libs(self):
        # app -> libb0.1 (shared) -> liba0.1 (shared)
        self.recipe_cache("liba/0.1", option_shared=True)
        libb = GenConanfile().with_requirement("liba/0.1", transitive_headers=True,
                                               transitive_libs=True)
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

        # node, headers, lib, build, run
        # Default for app->liba is that it doesn't link, libb shared will isolate symbols by default
        _check_transitive(app, [(libb, True, True, False, True),
                                (liba, True, True, False, True)])
        _check_transitive(libb, [(liba, True, True, False, True)])

    def test_middle_shared_up_static(self):
        # app -> libb0.1 (shared) -> liba0.1 (static)
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

        # node, headers, lib, build, run
        _check_transitive(app, [(libb, True, True, False, True),
                                (liba, False, False, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_middle_shared_up_static_transitive_headers(self):
        # app -> libb0.1 (shared) -> liba0.1 (static)
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

        # node, headers, lib, build, run
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

        # node, headers, lib, build, run
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

        # node, headers, lib, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, True, True, False, True)])
        _check_transitive(libb, [(liba, True, True, False, True)])

    def test_private(self):
        # app -> libb0.1 -(private) -> liba0.1
        self.recipe_cache("liba/0.1")
        libb = GenConanfile().with_requirement("liba/0.1", visible=False)
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

        # node, headers, lib, build, run
        _check_transitive(app, [(libb, True, True, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])

    def test_generic_library_without_shared_option(self):
        # app -> libb0.1 -> liba0.1 (library without shared option)
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("library"))
        libb = GenConanfile().with_requirement("liba/0.1")
        self.recipe_conanfile("libb/0.1", libb)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        with pytest.raises(ConanException) as exc:
            self.build_consumer(consumer)
        assert "liba/0.1: Package type is 'library', but no 'shared' option declared" in str(exc)

    def test_build_script_requirement(self):
        # app -> libb0.1 -br-> liba0.1 (build-scripts)
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("build-scripts"))
        self.recipe_conanfile("libb/0.1", GenConanfile().with_tool_requirement("liba/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        # node, headers, lib, build, run
        _check_transitive(app, [(libb, True, True, False, False)])
        _check_transitive(libb, [(liba, False, False, True, True)])

    @parameterized.expand([("application",), ("shared-library",), ("static-library",),
                           ("header-library",), ("build-scripts",), (None,)])
    def test_generic_build_require_adjust_run_with_package_type(self, package_type):
        # app --br-> cmake (app)
        self.recipe_conanfile("cmake/0.1", GenConanfile().with_package_type(package_type))
        # build require with run=None by default
        consumer = self.recipe_consumer("app/0.1", build_requires=["cmake/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        cmake = app.dependencies[0].dst

        # node, headers, lib, build, run
        run = package_type in ("application", "shared-library", "build-scripts")
        _check_transitive(app, [(cmake, False, False, True, run)])

    def test_direct_header_only(self):
        # app -> liba0.1 (header_only)
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("header-library"))
        consumer = self.recipe_consumer("app/0.1", ["liba/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        liba = app.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[liba])
        self._check_node(liba, "liba/0.1#123", dependents=[app])

        # node, headers, lib, build, run
        _check_transitive(app, [(liba, True, False, False, False)])

    def test_header_only(self):
        # app -> libb0.1 -> liba0.1 (header_only)
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("header-library"))
        libb = GenConanfile().with_requirement("liba/0.1")
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

        # node, headers, lib, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (liba, False, False, False, False)])
        _check_transitive(libb, [(liba, True, False, False, False)])

    def test_header_only_with_transitives(self):
        # app -> liba0.1(header) -> libb0.1 (static)
        #             \-----------> libc0.1 (shared)
        self.recipe_conanfile("libb/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_package_type("shared-library"))
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("header-library")
                                                        .with_requires("libb/0.1", "libc/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["liba/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        liba = app.dependencies[0].dst
        libb = liba.dependencies[0].dst
        libc = liba.dependencies[1].dst

        self._check_node(app, "app/0.1", deps=[liba])
        self._check_node(liba, "liba/0.1#123", deps=[libb, libc], dependents=[app])
        self._check_node(libb, "libb/0.1#123", dependents=[liba])
        self._check_node(libc, "libc/0.1#123", dependents=[liba])

        # node, headers, lib, build, run
        _check_transitive(app, [(liba, True, False, False, False),
                                (libb, True, True, False, False),
                                (libc, True, True, False, True)])
        _check_transitive(liba, [(libb, True, True, False, False),
                                 (libc, True, True, False, True)])

    def test_multiple_header_only_with_transitives(self):
        # app -> libd0.1(header) -> liba0.1(header) -> libb0.1 (static)
        #                               \-----------> libc0.1 (shared)
        self.recipe_conanfile("libb/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_package_type("shared-library"))
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("header-library")
                              .with_requires("libb/0.1", "libc/0.1"))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_package_type("header-library")
                              .with_requires("liba/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        liba = libd.dependencies[0].dst
        libb = liba.dependencies[0].dst
        libc = liba.dependencies[1].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", deps=[libb, libc], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", dependents=[liba])
        self._check_node(libc, "libc/0.1#123", dependents=[liba])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, False, False, False),
                                (liba, True, False, False, False),
                                (libb, True, True, False, False),
                                (libc, True, True, False, True)])
        _check_transitive(libd, [(liba, True, False, False, False),
                                 (libb, True, True, False, False),
                                 (libc, True, True, False, True)])
        _check_transitive(liba, [(libb, True, True, False, False),
                                 (libc, True, True, False, True)])

    def test_static_multiple_header_only_with_transitives(self):
        # app -> libd0.1(static) -> liba0.1(header) -> libb0.1 (static)
        #                               \-----------> libc0.1 (shared)
        self.recipe_conanfile("libb/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_package_type("shared-library"))
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("header-library")
                              .with_requires("libb/0.1", "libc/0.1"))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_package_type("static-library")
                              .with_requires("liba/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        liba = libd.dependencies[0].dst
        libb = liba.dependencies[0].dst
        libc = liba.dependencies[1].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", deps=[libb, libc], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", dependents=[liba])
        self._check_node(libc, "libc/0.1#123", dependents=[liba])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, True, False, False),
                                (liba, False, False, False, False),
                                (libb, False, True, False, False),
                                (libc, False, True, False, True)])
        _check_transitive(libd, [(liba, True, False, False, False),
                                 (libb, True, True, False, False),
                                 (libc, True, True, False, True)])
        _check_transitive(liba, [(libb, True, True, False, False),
                                 (libc, True, True, False, True)])

    def test_multiple_levels_transitive_headers(self):
        # app -> libcc0.1 -> libb0.1  -> liba0.1
        self.recipe_cache("liba/0.1")
        self.recipe_conanfile("libb/0.1", GenConanfile().with_package_type("static-library")
                                                        .with_requirement("liba/0.1",
                                                                          transitive_headers=True))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_package_type("static-library")
                                                        .with_requirement("libb/0.1",
                                                                          transitive_headers=True))
        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libc, True, True, False, False),
                                (libb, True, True, False, False),
                                (liba, True, True, False, False)])


class TestLinearFourLevels(GraphManagerTest):
    def test_default(self):
        # app -> libc/0.1 -> libb0.1  -> liba0.1
        self.recipe_conanfile("liba/0.1", GenConanfile())
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("libb/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libc, True, True, False, False),
                                (libb, True, True, False, False),
                                (liba, True, True, False, False)])

    def test_negate_headers(self):
        # app -> libc/0.1 -> libb0.1  -(not headers)-> liba0.1
        # So nobody depends on the headers downstream
        self.recipe_conanfile("liba/0.1", GenConanfile())
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1", headers=False))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("libb/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(libc, [(libb, True, True, False, False),
                                 (liba, False, True, False, False)])

        _check_transitive(app, [(libc, True, True, False, False),
                                (libb, True, True, False, False),
                                (liba, False, True, False, False)])

    @parameterized.expand([("static-library", ),
                           ("shared-library", )])
    def test_libraries_transitive_headers(self, library_type):
        # app -> libc/0.1 -> libb0.1  -> liba0.1
        # All with transitive_headers, the final application shoud get all headers
        # https://github.com/conan-io/conan/issues/12504
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type(library_type))
        self.recipe_conanfile("libb/0.1",
                              GenConanfile().with_package_type(library_type)
                                            .with_requirement("liba/0.1", transitive_headers=True))
        self.recipe_conanfile("libc/0.1",
                              GenConanfile().with_package_type(library_type)
                                            .with_requirement("libb/0.1", transitive_headers=True))
        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        if library_type == "shared-library":
            _check_transitive(app, [(libc, True, True, False, True),
                                    (libb, True, False, False, True),
                                    (liba, True, False, False, True)])
        else:  # Both static and unknown behave the same
            _check_transitive(app, [(libc, True, True, False, False),
                                    (libb, True, True, False, False),
                                    (liba, True, True, False, False)])

    def test_negate_libs(self):
        # app -> libc/0.1 -> libb0.1  -> liba0.1
        # even if all are static, we want to disable the propagation of one static lib downstream
        # because only the headers are used
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libb/0.1",
                              GenConanfile().with_package_type("static-library")
                                            .with_requirement("liba/0.1", libs=False))
        self.recipe_conanfile("libc/0.1",
                              GenConanfile().with_package_type("static-library")
                                            .with_requirement("libb/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(libb, [(liba, True, False, False, False)])
        _check_transitive(libc, [(libb, True, True, False, False),
                                 (liba, False, False, False, False)])

        _check_transitive(app, [(libc, True, True, False, False),
                                (libb, False, True, False, False),
                                (liba, False, False, False, False)])

    def test_disable_transitive_libs(self):
        # app -> libc/0.1 -> libb0.1  -> liba0.1
        # even if all are static, we want to disable the propagation of one static lib downstream
        # Maybe we are re-archiving
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libb/0.1",
                              GenConanfile().with_package_type("static-library")
                                            .with_requirement("liba/0.1", transitive_libs=False))
        self.recipe_conanfile("libc/0.1",
                              GenConanfile().with_package_type("static-library")
                                            .with_requirement("libb/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(libb, [(liba, True, True, False, False)])
        _check_transitive(libc, [(libb, True, True, False, False),
                                 (liba, False, False, False, False)])

        _check_transitive(app, [(libc, True, True, False, False),
                                (libb, False, True, False, False),
                                (liba, False, False, False, False)])

    def test_shared_depends_static_libraries(self):
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("static-library"))
        # Emulate a re-packaging, re-archiving static library
        self.recipe_conanfile("libb/0.1",
                              GenConanfile().with_package_type("shared-library")
                                            .with_requirement("liba/0.1"))
        self.recipe_conanfile("libc/0.1",
                              GenConanfile().with_package_type("static-library")
                                            .with_requirement("libb/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(libc, [(libb, True, True, False, True),
                                 (liba, False, False, False, False)])

        _check_transitive(app, [(libc, True, True, False, False),
                                (libb, False, True, False, True),
                                (liba, False, False, False, False)])

    def test_negate_run(self):
        # app -> libc/0.1 -> libb0.1  -> liba0.1
        # even if all are shared, we want to disable the propagation of one shared lib downstream
        # because only the headers are used
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("shared-library"))
        self.recipe_conanfile("libb/0.1",
                              GenConanfile().with_package_type("shared-library")
                                            .with_requirement("liba/0.1", run=False))
        self.recipe_conanfile("libc/0.1",
                              GenConanfile().with_package_type("shared-library")
                                            .with_requirement("libb/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(libb, [(liba, True, True, False, False)])
        _check_transitive(libc, [(libb, True, True, False, True),
                                 (liba, False, False, False, False)])

        _check_transitive(app, [(libc, True, True, False, True),
                                (libb, False, False, False, True),
                                (liba, False, False, False, False)])

    def test_force_run(self):
        # app -> libc/0.1 -> libb0.1  -> liba0.1
        # even if all are static, there is something in a static lib (files or whatever) that
        # is necessary at runtime
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libb/0.1",
                              GenConanfile().with_package_type("static-library")
                                            .with_requirement("liba/0.1", run=True))
        self.recipe_conanfile("libc/0.1",
                              GenConanfile().with_package_type("static-library")
                                            .with_requirement("libb/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(libb, [(liba, True, True, False, True)])
        _check_transitive(libc, [(libb, True, True, False, False),
                                 (liba, False, True, False, True)])

        _check_transitive(app, [(libc, True, True, False, False),
                                (libb, False, True, False, False),
                                (liba, False, True, False, True)])

    @parameterized.expand([(True,),
                           (False,)])
    def test_header_only_run(self, run):
        # app -> libc/0.1 -> libb0.1  -> liba0.1
        # many header-onlys
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("header-library"))
        self.recipe_conanfile("libb/0.1",
                              GenConanfile().with_package_type("header-library")
                                            .with_requirement("liba/0.1", run=run))
        self.recipe_conanfile("libc/0.1",
                              GenConanfile().with_package_type("header-library")
                                            .with_requirement("libb/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(libb, [(liba, True, False, False, run)])
        _check_transitive(libc, [(libb, True, False, False, False),
                                 (liba, True, False, False, run)])

        _check_transitive(app, [(libc, True, False, False, False),
                                (libb, True, False, False, False),
                                (liba, True, False, False, run)])

    def test_intermediate_header_only(self):
        # app -> libc/0.1 (static) -> libb0.1 (header) -> liba0.1 (static)
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libb/0.1",  GenConanfile().with_package_type("header-library")
                                                         .with_requirement("liba/0.1"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_package_type("static-library")
                                                        .with_requirement("libb/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(libb, [(liba, True, True, False, False)])
        _check_transitive(libc, [(libb, True, False, False, False),
                                 (liba, True, True, False, False)])

        _check_transitive(app, [(libc, True, True, False, False),
                                (libb, False, False, False, False),
                                (liba, False, True, False, False)])


class TestLinearFiveLevelsHeaders(GraphManagerTest):
    def test_all_header_only(self):
        # app -> libd/0.1 -> libc/0.1 -> libb0.1  -> liba0.1
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("header-library"))
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1")
                                                        .with_package_type("header-library"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("libb/0.1")
                                                        .with_package_type("header-library"))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_requirement("libc/0.1")
                                                        .with_package_type("header-library"))
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libc = libd.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, False, False, False),
                                (libc, True, False, False, False),
                                (libb, True, False, False, False),
                                (liba, True, False, False, False)])

    def test_all_header_only_aggregating_libc(self):
        # libc is copying and pasting the others headers at build time, creating re-distribution
        # app -> libd/0.1 -> libc/0.1 -(transitive_headers=FALSE)-> libb0.1  -> liba0.1
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("header-library"))
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1")
                                                        .with_package_type("header-library"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("libb/0.1",
                                                                          transitive_headers=False)
                                                        .with_package_type("header-library"))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_requirement("libc/0.1")
                                                        .with_package_type("header-library"))
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libc = libd.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, False, False, False),
                                (libc, True, False, False, False),
                                (libb, False, False, False, False),
                                (liba, False, False, False, False)])

    def test_first_header_only(self):
        # app -> libd/0.1(header) -> libc/0.1 -> libb0.1  -> liba0.1
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1")
                                                        .with_package_type("static-library"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("libb/0.1")
                                                        .with_package_type("static-library"))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_requirement("libc/0.1")
                                                        .with_package_type("header-library"))
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libc = libd.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, False, False, False),
                                (libc, True, True, False, False),
                                (libb, False, True, False, False),
                                (liba, False, True, False, False)])

    def test_first_header_only_transitive_headers_b(self):
        # app -> libd/0.1(header) -> libc/0.1 -(transitive_headers=T)-> libb0.1  -> liba0.1
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1")
                                                        .with_package_type("static-library"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("libb/0.1",
                                                                          transitive_headers=True)
                                                        .with_package_type("static-library"))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_requirement("libc/0.1")
                                                        .with_package_type("header-library"))
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libc = libd.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, False, False, False),
                                (libc, True, True, False, False),
                                (libb, True, True, False, False),
                                (liba, False, True, False, False)])

    def test_first_header_only_transitive_headers_b_a(self):
        # app -> libd/0.1(header) -> libc/0.1 -(transitive_headers=T)-> libb0.1 -(transitive_headers=T)-> liba0.1
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1",
                                                                          transitive_headers=True)
                                                        .with_package_type("static-library"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("libb/0.1",
                                                                          transitive_headers=True)
                                                        .with_package_type("static-library"))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_requirement("libc/0.1")
                                                        .with_package_type("header-library"))
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libc = libd.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, False, False, False),
                                (libc, True, True, False, False),
                                (libb, True, True, False, False),
                                (liba, True, True, False, False)])

    def test_first_header_only_reject_libs(self):
        # Like Libc knows it only uses headers from libb
        # app -> libd/0.1(header) -> libc/0.1 -(libs=False)-> libb0.1  -> liba0.1
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1")
                                                        .with_package_type("static-library"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("libb/0.1", libs=False)
                                                        .with_package_type("static-library"))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_requirement("libc/0.1")
                                                        .with_package_type("header-library"))
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libc = libd.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, False, False, False),
                                (libc, True, True, False, False),
                                (libb, False, False, False, False),
                                (liba, False, False, False, False)])

    def test_d_b_header_only(self):
        # app -> libd/0.1(header) -> libc/0.1 -> libb0.1(header)  -> liba0.1
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1")
                                                        .with_package_type("header-library"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("libb/0.1")
                                                        .with_package_type("static-library"))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_requirement("libc/0.1")
                                                        .with_package_type("header-library"))
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libc = libd.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, False, False, False),
                                (libc, True, True, False, False),
                                (libb, False, False, False, False),
                                (liba, False, True, False, False)])

    def test_d_b_header_only_transitive_headers_b(self):
        # app -> libd/0.1(header) -> libc/0.1 -(transitive_headers=T)-> libb0.1(header)  -> liba0.1
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1")
                                                        .with_package_type("header-library"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("libb/0.1",
                                                                          transitive_headers=True)
                                                        .with_package_type("static-library"))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_requirement("libc/0.1")
                                                        .with_package_type("header-library"))
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libc = libd.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, False, False, False),
                                (libc, True, True, False, False),
                                (libb, True, False, False, False),
                                (liba, True, True, False, False)])

    def test_visible_transitivity(self):
        # app -> libd/0.1 -> libc/0.1 -(visible=False)-> libb0.1  -> liba0.1
        self.recipe_conanfile("liba/0.1", GenConanfile())
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("libb/0.1",
                                                                          visible=False))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_requirement("libc/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libc = libd.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, True, False, False),
                                (libc, True, True, False, False)])
        _check_transitive(libd, [(libc, True, True, False, False)])
        _check_transitive(libc, [(libb, True, True, False, False),
                                 (liba, True, True, False, False)])

    def test_visible_build_transitivity(self):
        # app -> libd/0.1 -> libc/0.1 -(visible=True, build=True)-> libb0.1  -> liba0.1
        self.recipe_conanfile("liba/0.1", GenConanfile())
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("libb/0.1", build=True))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_requirement("libc/0.1"))
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libc = libd.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, True, False, False),
                                (libc, True, True, False, False),
                                (libb, False, False, True, False)])
        _check_transitive(libd, [(libc, True, True, False, False),
                                 (libb, False, False, True, False)])
        _check_transitive(libc, [(libb, True, True, True, False)])


class TestLinearFiveLevelsLibraries(GraphManagerTest):
    def test_all_static(self):
        # app -> libd/0.1 -> libc/0.1 -> libb0.1  -> liba0.1
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1")
                                                        .with_package_type("static-library"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("libb/0.1")
                                                        .with_package_type("static-library"))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_requirement("libc/0.1")
                                                        .with_package_type("static-library"))
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libc = libd.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, True, False, False),
                                (libc, False, True, False, False),
                                (libb, False, True, False, False),
                                (liba, False, True, False, False)])

    def test_libc_aggregating_static(self):
        # Lets think libc is re-linking its dependencies in a single .lib
        # app -> libd/0.1 -> libc/0.1 -(transitive_libs=False)-> libb0.1  -> liba0.1
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("static-library"))
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1")
                                                        .with_package_type("static-library"))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("libb/0.1",
                                                                          transitive_libs=False)
                                                        .with_package_type("static-library"))
        self.recipe_conanfile("libd/0.1", GenConanfile().with_requirement("libc/0.1")
                                                        .with_package_type("static-library"))
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libc = libd.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, True, False, False),
                                (libc, False, True, False, False),
                                (libb, False, False, False, False),
                                (liba, False, False, False, False)])


class TestDiamond(GraphManagerTest):

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

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

        _check_transitive(app, [(libb, True, True, False, False),
                                (libc, True, True, False, False),
                                (liba, True, True, False, False)])

    @parameterized.expand([(True, ), (False, )])
    def test_diamond_additive(self, order):
        # app -> libb0.1 ---------> liba0.1
        #    \-> libc0.1 (run=True)->/
        self.recipe_cache("liba/0.1")
        if order:
            self.recipe_cache("libb/0.1", ["liba/0.1"])
            self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("liba/0.1", run=True))
        else:
            self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1", run=True))
            self.recipe_cache("libc/0.1", ["liba/0.1"])

        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

        _check_transitive(app, [(libb, True, True, False, False),
                                (libc, True, True, False, False),
                                (liba, True, True, False, True)])

    def test_half_diamond(self):
        # app -----------> liba0.1
        #    \-> libc0.1 ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["liba/0.1", "libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        liba = app.dependencies[0].dst
        libc = app.dependencies[1].dst

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[liba, libc])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[app, libc])

        # Order seems to be link order
        _check_transitive(app, [(libc, True, True, False, False),
                                (liba, True, True, False, False)])
        # Both requires of app are direct! https://github.com/conan-io/conan/pull/12388
        for require in app.transitive_deps.keys():
            assert require.direct is True

    def test_half_diamond_reverse(self):
        # same as above, just swap order of declaration
        # app -->libc0.1--> liba0.1
        #    \-------------->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libc/0.1", "liba/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        liba = app.dependencies[1].dst

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[liba, libc])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[app, libc])

        # Order seems to be link order, constant irrespective of declaration order, good
        _check_transitive(app, [(libc, True, True, False, False),
                                (liba, True, True, False, False)])
        # Both requires of app are direct! https://github.com/conan-io/conan/pull/12388
        for require in app.transitive_deps.keys():
            assert require.direct is True

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

        # node, headers, lib, build, run
        _check_transitive(app, [(libb, True, True, False, True),
                                (libc, True, True, False, True),
                                (liba, False, False, False, False)])
        _check_transitive(libb, [(liba, True, True, False, False)])
        _check_transitive(libc, [(liba, True, True, False, False)])

    def test_private(self):
        # app -> libd0.1 -(private)-> libb0.1 -> liba0.1
        #            \ ---(private)-> libc0.1 --->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        libd = GenConanfile().with_requirement("libb/0.1", visible=False)
        libd.with_requirement("libc/0.1", visible=False)
        self.recipe_conanfile("libd/0.1", libd)
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libb = libd.dependencies[0].dst
        libc = libd.dependencies[1].dst
        liba = libb.dependencies[0].dst
        liba2 = libc.dependencies[0].dst

        assert liba is liba2

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libb, libc], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libd])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[libd])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

        # node, headers, lib, build, run
        _check_transitive(app, [(libd, True, True, False, False)])
        _check_transitive(libd, [(libb, True, True, False, False),
                                 (libc, True, True, False, False),
                                 (liba, True, True, False, False)])

    def test_shared_static_private(self):
        # app -> libb0.1 (shared) -(private)-> liba0.1 (static)
        #    \-> libc0.1 (shared) -> liba0.2 (static)
        # This private allows to avoid the liba conflict
        self.recipe_cache("liba/0.1", option_shared=False)
        self.recipe_cache("liba/0.2", option_shared=False)
        libb = GenConanfile().with_requirement("liba/0.1", visible=False)
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

        # node, headers, lib, build, run
        _check_transitive(app, [(libb, True, True, False, True),
                                (libc, True, True, False, True),
                                (liba2, False, False, False, False)])
        _check_transitive(libb, [(liba1, True, True, False, False)])
        _check_transitive(libc, [(liba2, True, True, False, False)])

    def test_diamond_conflict(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 -> liba0.2
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.2"])

        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])
        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphConflictError

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba1 = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba1], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[], dependents=[app])
        self._check_node(liba1, "liba/0.1#123", dependents=[libb])

    def test_shared_conflict_shared(self):
        # app -> libb0.1 (shared) -> liba0.1 (shared)
        #    \-> libc0.1 (shared) -> liba0.2 (shared)
        self.recipe_cache("liba/0.1", option_shared=True)
        self.recipe_cache("liba/0.2", option_shared=True)
        self.recipe_cache("libb/0.1", ["liba/0.1"], option_shared=True)
        self.recipe_cache("libc/0.1", ["liba/0.2"], option_shared=True)
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])

        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphConflictError

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba1 = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba1], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[], dependents=[app])
        self._check_node(liba1, "liba/0.1#123", dependents=[libb])

    def test_private_conflict(self):
        # app -> libd0.1 -(private)-> libb0.1 -> liba0.1
        #            \ ---(private)-> libc0.1 -> liba0.2
        #
        # private requires do not avoid conflicts at the node level, only downstream
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.2"])
        libd = GenConanfile().with_requirement("libb/0.1", visible=False)
        libd.with_requirement("libc/0.1", visible=False)
        self.recipe_conanfile("libd/0.1", libd)
        consumer = self.recipe_consumer("app/0.1", ["libd/0.1"])

        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphConflictError

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libd = app.dependencies[0].dst
        libb = libd.dependencies[0].dst
        libc = libd.dependencies[1].dst
        liba1 = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libd])
        self._check_node(libd, "libd/0.1#123", deps=[libb, libc], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba1], dependents=[libd])
        self._check_node(libc, "libc/0.1#123", deps=[], dependents=[libd])
        self._check_node(liba1, "liba/0.1#123", dependents=[libb])

    def test_diamond_transitive_private(self):
        # https://github.com/conan-io/conan/issues/13630
        # libc0.1 ----------> liba0.1 --(private) -> zlib/1.0
        #      \-> --(libb---->/

        self.recipe_cache("zlib/0.1")
        self.recipe_conanfile("liba/0.1", GenConanfile("liba", "0.1")
                              .with_requirement("zlib/0.1", visible=False))
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.1", "libb/0.1"])
        consumer = self.consumer_conanfile(GenConanfile("libc", "0.1")
                                           .with_requires("liba/0.1", "libb/0.1"))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        libc = deps_graph.root
        liba = libc.dependencies[0].dst
        libb = libc.dependencies[1].dst
        liba1 = libb.dependencies[0].dst
        zlib = liba.dependencies[0].dst

        assert liba is liba1
        # TODO: No Revision??? Because of consumer?
        self._check_node(libc, "libc/0.1", deps=[liba, libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc], deps=[zlib])
        self._check_node(zlib, "zlib/0.1#123", dependents=[liba])

        _check_transitive(libb, [(liba, True, True, False, False)])
        _check_transitive(libc, [(libb, True, True, False, False),
                                 (liba, True, True, False, False)])

    def test_private_transitive_headers_no_conflict(self):
        # https://github.com/conan-io/conan/issues/15559
        # app -->liba/0.1 -(private)-> spdlog/0.1(header-only) -> fmt/0.1 (header-only)
        #   \ --------------------------------------------------> fmt/0.2
        self.recipe_conanfile("fmt/0.1",
                              GenConanfile("fmt", "0.1").with_package_type("header-library"))
        self.recipe_conanfile("fmt/0.2", GenConanfile("fmt", "0.2"))
        self.recipe_conanfile("spdlog/0.1",
                              GenConanfile("spdlog", "0.1").with_package_type("header-library")
                                                           .with_requires("fmt/0.1"))
        self.recipe_conanfile("liba/0.1",
                              GenConanfile("liba", "0.2").with_requirement("spdlog/0.1",
                                                                           visible=False))
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1")
                                           .with_requires("liba/0.1", "fmt/0.2"))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        liba = app.dependencies[0].dst
        spdlog = liba.dependencies[0].dst
        fmt01 = spdlog.dependencies[0].dst
        fmt02 = app.dependencies[1].dst

        self._check_node(app, "app/0.1", deps=[liba, fmt02])
        self._check_node(liba, "liba/0.1#123", deps=[spdlog], dependents=[app])
        self._check_node(spdlog, "spdlog/0.1#123", deps=[fmt01], dependents=[liba])
        self._check_node(fmt01, "fmt/0.1#123", deps=[], dependents=[spdlog])
        self._check_node(fmt02, "fmt/0.2#123", dependents=[app])

        # node, headers, lib, build, run
        _check_transitive(app, [(liba, True, True, False, False),
                                (fmt02, True, True, False, False)])


class TestDiamondMultiple(GraphManagerTest):

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

        self._check_node(app, "app/0.1", deps=[libe, libf])
        self._check_node(libe, "libe/0.1#123", deps=[libd], dependents=[app])
        self._check_node(libf, "libf/0.1#123", deps=[libd], dependents=[app])
        self._check_node(libd, "libd/0.1#123", deps=[libb, libc], dependents=[libe, libf])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libd])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

        _check_transitive(app, [(libe, True, True, False, False),
                                (libf, True, True, False, False),
                                (libd, True, True, False, False),
                                (libb, True, True, False, False),
                                (libc, True, True, False, False),
                                (liba, True, True, False, False)])

    def test_consecutive_diamonds_private(self):
        # app -> libe0.1 ---------> libd0.1 ---> libb0.1 ---> liba0.1
        #    \-> (private)->libf0.1 ->/    \-private-> libc0.1 ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.1"])
        self._cache_recipe("libd/0.1", GenConanfile().with_require("libb/0.1")
                           .with_requirement("libc/0.1", visible=False))
        self.recipe_cache("libe/0.1", ["libd/0.1"])
        self.recipe_cache("libf/0.1", ["libd/0.1"])
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_require("libe/0.1")
                                           .with_requirement("libf/0.1", visible=False))

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(7, len(deps_graph.nodes))
        app = deps_graph.root
        libe = app.dependencies[0].dst
        libf = app.dependencies[1].dst
        libd = libe.dependencies[0].dst
        libb = libd.dependencies[0].dst
        libc = libd.dependencies[1].dst
        liba = libc.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libe, libf])
        self._check_node(libe, "libe/0.1#123", deps=[libd], dependents=[app])
        self._check_node(libf, "libf/0.1#123", deps=[libd], dependents=[app])
        self._check_node(libd, "libd/0.1#123", deps=[libb, libc], dependents=[libe, libf])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libd])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

        # FIXME: In this case the order seems a bit broken
        _check_transitive(app, [(libe, True, True, False, False),
                                (libf, True, True, False, False),
                                (libd, True, True, False, False),
                                (libb, True, True, False, False),
                                (liba, True, True, False, False),
                                ])

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

        self._check_node(app, "app/0.1", deps=[libb, libc, libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app])
        self._check_node(libd, "libd/0.1#123", deps=[liba], dependents=[app])
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

        self._check_node(app, "app/0.1", deps=[libb, libc, libd])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba], dependents=[app, libd])
        self._check_node(libd, "libd/0.1#123", deps=[libc], dependents=[app])
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

        self._check_node(app, "app/0.1", deps=[libd, libc, libb])
        self._check_node(libd, "libd/0.1#123", dependents=[app, libc])
        self._check_node(libb, "libb/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[libd], dependents=[app, libb])

    def test_loop(self):
        # app -> libc0.1 -> libb0.1 -> liba0.1 ->|
        #             \<-------------------------|
        self.recipe_cache("liba/0.1", ["libc/0.1"])
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["libb/0.1"])

        consumer = self.recipe_consumer("app/0.1", ["libc/0.1"])

        deps_graph = self.build_consumer(consumer, install=False)
        # TODO: Better error modeling
        assert type(deps_graph.error) == GraphLoopError

        self.assertEqual(4, len(deps_graph.nodes))

        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", deps=[], dependents=[libb])


class TransitiveOverridesGraphTest(GraphManagerTest):

    def test_diamond(self):
        # app -> libb0.1 -> liba0.2 (overriden to lib0.2)
        #    \-> --------- ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_require("libb/0.1")
                                           .with_requirement("liba/0.2", force=True))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = app.dependencies[1].dst
        liba2 = libb.dependencies[0].dst

        assert liba is liba2

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libb, liba])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.2#123", dependents=[libb, app])

    def test_diamond_conflict(self):
        # app -> libb0.1 -> liba0.2 (overriden to lib0.2)
        #    \-> --------- ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "liba/0.2"])

        deps_graph = self.build_consumer(consumer, install=False)
        assert deps_graph.error is not False
        assert type(deps_graph.error) == GraphConflictError

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[], dependents=[app])

    def test_build_script_no_conflict(self):
        # app -> libb0.1 -> liba0.1 (build-scripts)
        #    \-> libc0.1 -> liba0.2
        self.recipe_conanfile("liba/0.1", GenConanfile().with_package_type("build-scripts"))
        self.recipe_conanfile("liba/0.2", GenConanfile())
        self.recipe_conanfile("libb/0.1",
                              GenConanfile().with_tool_requirement("liba/0.1", run=False))
        self.recipe_conanfile("libc/0.1", GenConanfile().with_requirement("liba/0.2"))
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])

        deps_graph = self.build_consumer(consumer)

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba1 = libb.dependencies[0].dst
        liba2 = libc.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[liba1], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[liba2], dependents=[app])
        self._check_node(liba1, "liba/0.1#123", dependents=[libb])
        self._check_node(liba2, "liba/0.2#123", dependents=[libc])

        # node, headers, lib, build, run
        _check_transitive(app, [(libb, True, True, False, False),
                                (libc, True, True, False, False),
                                (liba2, True, True, False, False)])
        _check_transitive(libb, [(liba1, False, False, True, False)])
        _check_transitive(libc, [(liba2, True, True, False, False)])

    def test_diamond_reverse_order(self):
        # foo ---------------------------------> dep1/2.0
        #   \ -> dep2/1.0--(dep1/1.0 overriden)-->/
        self.recipe_cache("dep1/1.0")
        self.recipe_cache("dep1/2.0")
        self.recipe_cache("dep2/1.0", ["dep1/1.0"])
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1")
                                           .with_requirement("dep1/2.0", force=True)
                                           .with_requirement("dep2/1.0"))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        dep1 = app.dependencies[0].dst
        dep2 = app.dependencies[1].dst

        self._check_node(app, "app/0.1", deps=[dep1, dep2])
        self._check_node(dep1, "dep1/2.0#123", deps=[], dependents=[app, dep2])
        self._check_node(dep2, "dep2/1.0#123", deps=[dep1], dependents=[app])

    def test_diamond_reverse_order_conflict(self):
        # foo ---------------------------------> dep1/2.0
        #   \ -> dep2/1.0--(dep1/1.0 overriden)-->/
        self.recipe_cache("dep1/1.0")
        self.recipe_cache("dep1/2.0")
        self.recipe_cache("dep2/1.0", ["dep1/1.0"])
        consumer = self.recipe_consumer("app/0.1", ["dep1/2.0", "dep2/1.0"])
        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphConflictError

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        dep1 = app.dependencies[0].dst
        dep2 = app.dependencies[1].dst
        self._check_node(app, "app/0.1", deps=[dep1, dep2])
        self._check_node(dep1, "dep1/2.0#123", deps=[], dependents=[app])
        # dep2 no dependency, it was not resolved due to conflict
        self._check_node(dep2, "dep2/1.0#123", deps=[], dependents=[app])

    def test_invisible_not_forced(self):
        # app -> libb0.1 -(visible=False)----> liba0.1 (NOT forced to lib0.2)
        #    \-> -----(force not used)-------> liba0.2
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1",
                                                                          visible=False))
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_require("libb/0.1")
                                           .with_requirement("liba/0.2", force=True))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba2 = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libb, liba2])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])
        self._check_node(liba2, "liba/0.2#123", dependents=[app])


class PureOverrideTest(GraphManagerTest):

    def test_diamond(self):
        # app -> libb0.1 -> liba0.2 (overriden to lib0.2)
        #    \-> ---(override)------ ->/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_require("libb/0.1")
                                           .with_requirement("liba/0.2", override=True))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.2#123", dependents=[libb])

    def test_discarded_override(self):
        # app ->---(override)------> liba0.2
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1")
                                           .with_requirement("liba/0.2", override=True))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(1, len(deps_graph.nodes))
        app = deps_graph.root
        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[])

    def test_invisible_not_overriden(self):
        # app -> libb0.1 -(visible=False)----> liba0.1 (NOT overriden to lib0.2)
        #    \-> -----(override not used)------->/
        self.recipe_cache("liba/0.1")
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requirement("liba/0.1",
                                                                          visible=False))
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_require("libb/0.1")
                                           .with_requirement("liba/0.2", override=True))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[app])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])

    def test_nested_overrides(self):
        # app -> libc0.1 ------> libb0.1 ------> liba0.1
        #  \          \-> --(override liba0.2)---->/
        #   \-> ---(override liba0.3)------------>/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("liba/0.3")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_conanfile("libc/0.1", GenConanfile("libc", "0.1")
                              .with_requirement("libb/0.1")
                              .with_requirement("liba/0.2", override=True))
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_require("libc/0.1")
                                           .with_requirement("liba/0.3", override=True))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.3#123", dependents=[libb])

    def test_override_solve_upstream_conflict(self):
        # app -> libc0.1 ------> libb0.1 ------> liba0.1
        #  \          \-> --(liba0.2 conflict)---->/
        #   \-> ---(override liba0.3)------------>/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("liba/0.3")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_conanfile("libc/0.1", GenConanfile("libc", "0.1")
                              .with_requires("libb/0.1", "liba/0.2"))
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_require("libc/0.1")
                                           .with_requirement("liba/0.3", override=True))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        # TODO: No Revision??? Because of consumer?
        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb, liba], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.3#123", dependents=[libb, libc])

    def test_override_not_used(self):
        # https://github.com/conan-io/conan/issues/13630
        # libc0.1 ----------> liba0.1 --(override) -> zlib/1.0
        #      \-> --(libb---->/

        self.recipe_conanfile("liba/0.1", GenConanfile("liba", "0.1")
                              .with_requirement("zlib/0.1", override=True))
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/0.1", "libb/0.1"])
        consumer = self.consumer_conanfile(GenConanfile("libc", "0.1")
                                           .with_requires("liba/0.1", "libb/0.1"))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        libc = deps_graph.root
        liba = libc.dependencies[0].dst
        libb = libc.dependencies[1].dst
        liba1 = libb.dependencies[0].dst

        assert liba is liba1
        # TODO: No Revision??? Because of consumer?
        self._check_node(libc, "libc/0.1", deps=[liba, libb])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc])

        _check_transitive(libb, [(liba, True, True, False, False)])
        _check_transitive(libc, [(libb, True, True, False, False),
                                 (liba, True, True, False, False)])


class PackageIDDeductions(GraphManagerTest):

    def test_static_dep_to_shared(self):
        # project -> app1 -> lib
        #    \---- > app2 --/

        self._cache_recipe("lib/0.1", GenConanfile())
        self._cache_recipe("app1/0.1", GenConanfile().with_requirement("lib/0.1"))
        self._cache_recipe("app2/0.1", GenConanfile().with_requirement("lib/0.1"))

        deps_graph = self.build_graph(GenConanfile("project", "0.1")
                                      .with_requirement("app1/0.1", headers=False, libs=False,
                                                        build=False, run=True)
                                      .with_requirement("app2/0.1", headers=False, libs=False,
                                                        build=False, run=True)
                                      )

        self.assertEqual(4, len(deps_graph.nodes))
        project = deps_graph.root
        app1 = project.dependencies[0].dst
        app2 = project.dependencies[1].dst
        lib = app1.dependencies[0].dst
        lib2 = app2.dependencies[0].dst

        assert lib is lib2

        self._check_node(project, "project/0.1@", deps=[app1, app2], dependents=[])
        self._check_node(app1, "app1/0.1#123", deps=[lib], dependents=[project])
        self._check_node(app2, "app2/0.1#123", deps=[lib], dependents=[project])
        self._check_node(lib, "lib/0.1#123", deps=[], dependents=[app1, app2])

        # node, headers, lib, build, run
        _check_transitive(project, [(app1, False, False, False, True),
                                    (app2, False, False, False, True),
                                    (lib, False, False, False, False)])


class TestProjectApp(GraphManagerTest):
    """
    Emulating a project that can gather multiple applications and other resources and build a
    consistent graph, in which dependencies are same versions
    """
    def test_project_require_transitive(self):
        # project -> app1 -> lib
        #    \---- > app2 --/

        self._cache_recipe("lib/0.1", GenConanfile())
        self._cache_recipe("app1/0.1", GenConanfile().with_requirement("lib/0.1"))
        self._cache_recipe("app2/0.1", GenConanfile().with_requirement("lib/0.1"))

        deps_graph = self.build_graph(GenConanfile("project", "0.1")
                                      .with_requirement("app1/0.1", headers=False, libs=False,
                                                        build=False, run=True)
                                      .with_requirement("app2/0.1", headers=False, libs=False,
                                                        build=False, run=True)
                                      )

        self.assertEqual(4, len(deps_graph.nodes))
        project = deps_graph.root
        app1 = project.dependencies[0].dst
        app2 = project.dependencies[1].dst
        lib = app1.dependencies[0].dst
        lib2 = app2.dependencies[0].dst

        assert lib is lib2

        self._check_node(project, "project/0.1@", deps=[app1, app2], dependents=[])
        self._check_node(app1, "app1/0.1#123", deps=[lib], dependents=[project])
        self._check_node(app2, "app2/0.1#123", deps=[lib], dependents=[project])
        self._check_node(lib, "lib/0.1#123", deps=[], dependents=[app1, app2])

        # node, headers, lib, build, run
        _check_transitive(project, [(app1, False, False, False, True),
                                    (app2, False, False, False, True),
                                    (lib, False, False, False, False)])

    def test_project_require_transitive_conflict(self):
        # project -> app1 -> lib/0.1
        #    \---- > app2 -> lib/0.2

        self._cache_recipe("lib/0.1", GenConanfile())
        self._cache_recipe("lib/0.2", GenConanfile())
        self._cache_recipe("app1/0.1", GenConanfile().with_requirement("lib/0.1"))
        self._cache_recipe("app2/0.1", GenConanfile().with_requirement("lib/0.2"))

        deps_graph = self.build_graph(GenConanfile("project", "0.1")
                                      .with_requirement("app1/0.1", headers=False, libs=False,
                                                        build=False, run=True)
                                      .with_requirement("app2/0.1", headers=False, libs=False,
                                                        build=False, run=True),
                                      install=False)

        assert type(deps_graph.error) == GraphConflictError

    def test_project_require_apps_transitive(self):
        # project -> app1 (app type) -> lib
        #    \---- > app2 (app type) --/

        self._cache_recipe("lib/0.1", GenConanfile())
        self._cache_recipe("app1/0.1", GenConanfile().with_package_type("application").
                           with_requirement("lib/0.1"))
        self._cache_recipe("app2/0.1", GenConanfile().with_package_type("application").
                           with_requirement("lib/0.1"))

        deps_graph = self.build_graph(GenConanfile("project", "0.1").with_requires("app1/0.1",
                                                                                   "app2/0.1"))

        self.assertEqual(4, len(deps_graph.nodes))
        project = deps_graph.root
        app1 = project.dependencies[0].dst
        app2 = project.dependencies[1].dst
        lib = app1.dependencies[0].dst
        lib2 = app2.dependencies[0].dst

        assert lib is lib2

        self._check_node(project, "project/0.1@", deps=[app1, app2], dependents=[])
        self._check_node(app1, "app1/0.1#123", deps=[lib], dependents=[project])
        self._check_node(app2, "app2/0.1#123", deps=[lib], dependents=[project])
        self._check_node(lib, "lib/0.1#123", deps=[], dependents=[app1, app2])

        # node, headers, lib, build, run
        _check_transitive(project, [(app1, False, False, False, True),
                                    (app2, False, False, False, True),
                                    (lib, False, False, False, False)])

    def test_project_require_apps_transitive_conflict(self):
        # project -> app1 (app type) -> lib/0.1
        #    \---- > app2 (app type) -> lib/0.2

        self._cache_recipe("lib/0.1", GenConanfile())
        self._cache_recipe("lib/0.2", GenConanfile())
        self._cache_recipe("app1/0.1", GenConanfile().with_package_type("application").
                           with_requirement("lib/0.1"))
        self._cache_recipe("app2/0.1", GenConanfile().with_package_type("application").
                           with_requirement("lib/0.2"))

        deps_graph = self.build_graph(GenConanfile("project", "0.1").with_requires("app1/0.1",
                                                                                   "app2/0.1"),
                                      install=False)

        assert type(deps_graph.error) == GraphConflictError

    def test_project_require_private(self):
        # project -(!visible)-> app1 -> lib1
        #    \----(!visible)- > app2 -> lib2
        # This doesn't conflict on project, as lib1, lib2 do not include, link or public

        self._cache_recipe("lib/0.1", GenConanfile())
        self._cache_recipe("lib/0.2", GenConanfile())
        self._cache_recipe("app1/0.1", GenConanfile().with_requirement("lib/0.1"))
        self._cache_recipe("app2/0.1", GenConanfile().with_requirement("lib/0.2"))

        deps_graph = self.build_graph(GenConanfile("project", "0.1")
                                      .with_requirement("app1/0.1", headers=False, libs=False,
                                                        build=False, run=True, visible=False)
                                      .with_requirement("app2/0.1", headers=False, libs=False,
                                                        build=False, run=True, visible=False)
                                      )

        self.assertEqual(5, len(deps_graph.nodes))
        project = deps_graph.root
        app1 = project.dependencies[0].dst
        app2 = project.dependencies[1].dst
        lib1 = app1.dependencies[0].dst
        lib2 = app2.dependencies[0].dst

        assert lib1 is not lib2

        self._check_node(project, "project/0.1@", deps=[app1, app2], dependents=[])
        self._check_node(app1, "app1/0.1#123", deps=[lib1], dependents=[project])
        self._check_node(app2, "app2/0.1#123", deps=[lib2], dependents=[project])
        self._check_node(lib1, "lib/0.1#123", deps=[], dependents=[app1])
        self._check_node(lib2, "lib/0.2#123", deps=[], dependents=[app2])

        # node, headers, lib, build, run
        _check_transitive(project, [(app1, False, False, False, True),
                                    (lib1, False, False, False, False),
                                    (app2, False, False, False, True),
                                    (lib2, False, False, False, False)])
