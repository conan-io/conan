import textwrap

from parameterized import parameterized

from conans.client.graph.graph_error import GraphProvidesError
from test.integration.graph.core.graph_manager_base import GraphManagerTest
from test.integration.graph.core.graph_manager_test import _check_transitive
from conan.test.utils.tools import GenConanfile, TestClient


class TestProvidesTest(GraphManagerTest):

    def test_direct_conflict(self):
        # app (provides feature)-> libb0.1 (provides feature)
        self.recipe_conanfile("libb/0.1", GenConanfile().with_provides("feature"))
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_provides("feature").
                                           with_requires("libb/0.1"))
        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphProvidesError

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[], dependents=[app])

    def test_transitive_conflict(self):
        # app (provides feature)-> libb0.1 -> libc/0.1 (provides feature)
        self.recipe_conanfile("libc/0.1", GenConanfile().with_provides("feature"))
        self.recipe_conanfile("libb/0.1", GenConanfile().with_requires("libc/0.1"))
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_provides("feature").
                                           with_requires("libb/0.1"))
        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphProvidesError

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libb])
        self._check_node(libb, "libb/0.1#123", deps=[libc], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[], dependents=[libb])

    @parameterized.expand([(True,), (False,)])
    def test_branches_conflict(self, private):
        # app -> libb/0.1 (provides feature)
        #  \  -> libc/0.1 (provides feature)
        self.recipe_conanfile("libc/0.1", GenConanfile().with_provides("feature"))
        self.recipe_conanfile("libb/0.1", GenConanfile().with_provides("feature"))
        if private:
            consumer = self.consumer_conanfile(GenConanfile("app", "0.1").
                                               with_requirement("libb/0.1", visible=False).
                                               with_requirement("libc/0.1", visible=False))
        else:
            consumer = self.consumer_conanfile(GenConanfile("app", "0.1").
                                               with_requires("libb/0.1", "libc/0.1"))
        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphProvidesError

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst

        self._check_node(app, "app/0.1", deps=[libb, libc])
        self._check_node(libb, "libb/0.1#123", deps=[], dependents=[app])
        self._check_node(libc, "libc/0.1#123", deps=[], dependents=[app])

    def test_private_no_conflict(self):
        # app (provides libjpeg) -(private)-> br/v1 -(private)-> br_lib/v1(provides libjpeg)
        self.recipe_conanfile("br_lib/0.1", GenConanfile().with_provides("libjpeg"))
        self.recipe_conanfile("br/0.1", GenConanfile().with_requirement("br_lib/0.1", visible=False))
        path = self.consumer_conanfile(GenConanfile("app", "0.1").
                                       with_requirement("br/0.1", visible=False).
                                       with_provides("libjpeg"))

        deps_graph = self.build_consumer(path)
        self.assertEqual(3, len(deps_graph.nodes))

        app = deps_graph.root
        br = app.dependencies[0].dst
        br_lib = br.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[br])
        self._check_node(br, "br/0.1#123", deps=[br_lib], dependents=[app])
        self._check_node(br_lib, "br_lib/0.1#123", deps=[], dependents=[br])

        # node, include, link, build, run
        _check_transitive(app, [(br, True, True, False, False)])
        _check_transitive(br, [(br_lib, True, True, False, False)])

    def test_diamond_conflict(self):
        # app -> libb0.1 -> liba0.1
        #    \-> libc0.1 -> libd0.2 (provides liba)
        self.recipe_cache("liba/0.1")
        self.recipe_conanfile("libd/0.2", GenConanfile().with_provides("liba"))
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["libd/0.2"])

        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])
        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphProvidesError

        self.assertEqual(5, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba1 = libb.dependencies[0].dst
        libd2 = libc.dependencies[0].dst
        self._check_node(app, "app/0.1", deps=[libb, libc])
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
        assert type(deps_graph.error) == GraphProvidesError

        self.assertEqual(4, len(deps_graph.nodes))

        app = deps_graph.root
        libc = app.dependencies[0].dst
        libb = libc.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[libc])
        self._check_node(libc, "libc/0.1#123", deps=[libb], dependents=[app])
        self._check_node(libb, "libb/0.1#123", deps=[liba], dependents=[libc])
        self._check_node(liba, "liba/0.1#123", dependents=[libb])


class ProvidesBuildRequireTest(GraphManagerTest):
    def test_build_require_no_conflict(self):
        # app (provides libjpeg) -(build)-> br/v1 -> br_lib/v1(provides libjpeg)
        self.recipe_conanfile("br_lib/0.1", GenConanfile().with_provides("libjpeg"))
        self.recipe_cache("br/0.1", ["br_lib/0.1"])
        path = self.consumer_conanfile(GenConanfile("app", "0.1").with_tool_requires("br/0.1").
                                       with_provides("libjpeg"))

        deps_graph = self.build_consumer(path)
        self.assertEqual(3, len(deps_graph.nodes))

        app = deps_graph.root
        br = app.dependencies[0].dst
        br_lib = br.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[br])
        self._check_node(br, "br/0.1#123", deps=[br_lib], dependents=[app])
        self._check_node(br_lib, "br_lib/0.1#123", deps=[], dependents=[br])

        # node, include, link, build, run
        _check_transitive(app, [(br, False, False, True, True)])
        _check_transitive(br, [(br_lib, True, True, False, False)])

    def test_transitive_br_no_conflict(self):
        # app (provides libjpeg) -> lib/v1 -(br)-> br/v1(provides libjpeg)
        self.recipe_conanfile("br/0.1", GenConanfile().with_provides("libjpeg"))
        self.recipe_conanfile("lib/0.1", GenConanfile().with_tool_requires("br/0.1"))
        path = self.consumer_conanfile(GenConanfile("app", "0.1").with_requires("lib/0.1").
                                       with_provides("libjpeg"))

        deps_graph = self.build_consumer(path)
        self.assertEqual(3, len(deps_graph.nodes))

        app = deps_graph.root
        lib = app.dependencies[0].dst
        br = lib.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[lib])
        self._check_node(lib, "lib/0.1#123", deps=[br], dependents=[app])
        self._check_node(br, "br/0.1#123", deps=[], dependents=[lib])

        # node, include, link, build, run
        _check_transitive(app, [(lib, True, True, False, False)])
        _check_transitive(lib, [(br, False, False, True, True)])

    def test_transitive_test_require_conflict(self):
        # app (provides libjpeg) -(test)-> br/v1 -> br_lib/v1(provides libjpeg)
        self.recipe_conanfile("br_lib/0.1", GenConanfile().with_provides("libjpeg"))
        self.recipe_cache("br/0.1", ["br_lib/0.1"])
        path = self.consumer_conanfile(GenConanfile("app", "0.1").with_test_requires("br/0.1").
                                       with_provides("libjpeg"))

        deps_graph = self.build_consumer(path, install=False)

        assert type(deps_graph.error) == GraphProvidesError

        self.assertEqual(3, len(deps_graph.nodes))

        app = deps_graph.root
        br = app.dependencies[0].dst
        br_lib = br.dependencies[0].dst

        self._check_node(app, "app/0.1", deps=[br])
        self._check_node(br, "br/0.1#123", deps=[br_lib], dependents=[app])
        self._check_node(br_lib, "br_lib/0.1#123", deps=[], dependents=[br])

    def test_two_br_conflict(self):
        # app -(build)-> br1/v1 (provides libjpeg)
        #   \ -(build)-> br2/v1 (provides libjpeg)
        self.recipe_conanfile("br1/0.1", GenConanfile().with_provides("libjpeg"))
        self.recipe_conanfile("br2/0.1", GenConanfile().with_provides("libjpeg"))
        path = self.consumer_conanfile(GenConanfile("app", "0.1")
                                       .with_tool_requires("br1/0.1", "br2/0.1"))
        deps_graph = self.build_consumer(path, install=False)

        assert type(deps_graph.error) == GraphProvidesError

        self.assertEqual(3, len(deps_graph.nodes))

        app = deps_graph.root
        br1 = app.dependencies[0].dst
        br2 = app.dependencies[1].dst

        self._check_node(app, "app/0.1", deps=[br1, br2])
        self._check_node(br1, "br1/0.1#123", deps=[], dependents=[app])
        self._check_node(br2, "br2/0.1#123", deps=[], dependents=[app])


def test_conditional():
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Recipe(ConanFile):
            requires = 'req/v1'
            options = {'conflict': [True, False]}
            default_options = {'conflict': False}

            def configure(self):
                if self.options.conflict:
                    self.provides = 'libjpeg'

            def package_info(self):
                self.info.clear()
    """)
    t = TestClient(light=True)
    t.save({'requires.py': GenConanfile("req", "v1").with_provides("libjpeg"),
            'app.py': conanfile})
    t.run("create requires.py")
    t.run("install app.py --name=app --version=version")
    t.run("install app.py --name=app --version=version -o app/*:conflict=True", assert_error=True)
    assert "ERROR: Provide Conflict: Both 'app/version' and 'req/v1' provide 'libjpeg'" in t.out


def test_self_build_require():
    c = TestClient()
    conanfile = textwrap.dedent("""\
        from conan import ConanFile
        from conan.tools.build import cross_building

        class Pkg(ConanFile):
            name = "grpc"
            version = "0.1"
            settings = "os"
            provides = "grpc-impl"
            def build_requirements(self):
                if cross_building(self):
                    self.tool_requires("grpc/0.1")
        """)
    c.save({'conanfile.py': conanfile})
    c.run("create . -s os=Windows -s:b os=Windows")
    c.assert_listed_binary({"grpc/0.1": ("ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715", "Build")})
    c.run("create . -s os=Linux -s:b os=Windows --build=missing")
    c.assert_listed_binary({"grpc/0.1": ("9a4eb3c8701508aa9458b1a73d0633783ecc2270", "Build")})
    c.assert_listed_binary({"grpc/0.1": ("ebec3dc6d7f6b907b3ada0c3d3cdc83613a2b715", "Cache")},
                           build=True)


def test_name_provide_error_message():
    tc = TestClient(light=True)
    tc.save({"libjepg/conanfile.py": GenConanfile("libjpeg", "0.1"),
             "mozjpeg/conanfile.py": GenConanfile("mozjpeg", "0.1").with_provides("libjpeg")})
    tc.run("create libjepg")
    tc.run("create mozjpeg")

    tc.run("graph info --requires=mozjpeg/0.1 --requires=libjpeg/0.1", assert_error=True)
    # This used to report that None was provided, but now it reports the name of the provides
    assert "ERROR: Provide Conflict: Both 'libjpeg/0.1' and 'mozjpeg/0.1' provide '['libjpeg']'" in tc.out
