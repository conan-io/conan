from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_MISSING
from conans.test.assets.genconanfile import GenConanfile
from conans.test.integration.graph.core.wip.graph_manager_base import GraphManagerTest
from conans.test.utils.tools import TestClient


class TestVersionRanges(GraphManagerTest):

    def test_transitive(self):
        # app -> libb[>0.1]
        self.recipe_cache("libb/0.1")
        self.recipe_cache("libb/0.2")
        consumer = self.recipe_consumer("app/0.1", ["libb/[>=0.0]"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst

        self._check_node(libb, "libb/0.2#123", dependents=[app])
        self._check_node(app, "app/0.1", deps=[libb])

        assert libb.package_id == "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"

    def test_missing(self):
        # app -> libb[>0.1] (missing)
        consumer = self.recipe_consumer("app/0.1", ["libb/[>=0.0]"])

        deps_graph = self.build_consumer(consumer, install=False)

        assert deps_graph.error == "Cannot resolve version range libb/[>=0.0]"

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst

        self._check_node(libb, "libb/[>=0.0]", dependents=[app])
        self._check_node(app, "app/0.1", deps=[libb])

    def test_userchannel_no_match(self):
        # app -> libb[>0.1] (missing)
        self.recipe_cache("libb/0.1@user/channel")
        consumer = self.recipe_consumer("app/0.1", ["libb/[>=0.0]"])

        deps_graph = self.build_consumer(consumer, install=False)

        assert deps_graph.error == "Cannot resolve version range libb/[>=0.0]"

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst

        self._check_node(libb, "libb/[>=0.0]", dependents=[app])
        self._check_node(app, "app/0.1", deps=[libb])

    def test_required_userchannel_no_match(self):
        # app -> libb[>0.1] (missing)
        self.recipe_cache("libb/0.1")
        consumer = self.recipe_consumer("app/0.1", ["libb/[>=0.0]@user/channel"])

        deps_graph = self.build_consumer(consumer, install=False)

        assert deps_graph.error == "Cannot resolve version range libb/[>=0.0]@user/channel"

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst

        self._check_node(libb, "libb/[>=0.0]@user/channel", dependents=[app])
        self._check_node(app, "app/0.1", deps=[libb])

    def test_transitive_out_range(self):
        # app -> libb[>0.1] (missing)
        self.recipe_cache("libb/0.1")
        consumer = self.recipe_consumer("app/0.1", ["libb/[>1.0]"])

        deps_graph = self.build_consumer(consumer, install=False)

        assert deps_graph.error == "Cannot resolve version range libb/[>1.0]"

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        self._check_node(libb, "libb/[>1.0]", dependents=[app])
        self._check_node(app, "app/0.1", deps=[libb])


class TestVersionRangesDiamond(GraphManagerTest):
    def test_transitive(self):
        # app -> libb/0.1 -(range >1)-> liba/0.2
        #   \ -> libc/0.1 -(range <2)---/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/[>=0.0]"])
        self.recipe_cache("libc/0.1", ["liba/[<1.0]"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        self._check_node(libb, "libb/0.1#123", dependents=[app], deps=[liba])
        self._check_node(libc, "libc/0.1#123", dependents=[app], deps=[liba])
        self._check_node(app, "app/0.1", deps=[libb, libc])


def test_mixed_user_channel():
    # https://github.com/conan-io/conan/issues/7846
    t = TestClient(default_server_user=True)
    t.save({"conanfile.py": GenConanfile()})
    t.run("create . pkg/1.0@")
    t.run("create . pkg/1.1@")
    t.run("create . pkg/2.0@")
    t.run("create . pkg/1.0@user/testing")
    t.run("create . pkg/1.1@user/testing")
    t.run("create . pkg/2.0@user/testing")
    t.run("upload * --all --confirm")
    t.run("remove * -f")

    t.run('install "pkg/[>0 <2]@"')
    assert "pkg/1.1 from 'default' - Downloaded" in t.out
    t.run('install "pkg/[>0 <2]@user/testing"')
    assert "pkg/1.1@user/testing from 'default' - Downloaded" in t.out
