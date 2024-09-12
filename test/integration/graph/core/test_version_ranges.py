from collections import OrderedDict
import pytest

from conan.api.model import Remote
from conans.client.graph.graph_error import GraphConflictError, GraphMissingError
from conan.test.assets.genconanfile import GenConanfile
from test.integration.graph.core.graph_manager_base import GraphManagerTest
from conan.test.utils.tools import TestClient, TestServer, NO_SETTINGS_PACKAGE_ID


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

    def test_transitive_local_conditions(self):
        for v in ["0.1", "0.2", "0.3", "1.1", "1.1.2", "1.2.1", "2.1", "2.2.1"]:
            self.recipe_cache(f"libb/{v}")

        for expr, solution in [(">0.0", "2.2.1"),
                               (">0.1 <1", "0.3"),
                               (">0.1 <1||2.1", "2.1"),
                               ("", "2.2.1"),
                               ("~0", "0.3"),
                               ("~1", "1.2.1"),
                               ("~1.1", "1.1.2"),
                               ("~2", "2.2.1"),
                               ("~2.1", "2.1"),
                               ]:
            consumer = self.recipe_consumer("app/0.1", [f"libb/[{expr}]"])
            deps_graph = self.build_consumer(consumer)
            self.assertEqual(2, len(deps_graph.nodes))
            app = deps_graph.root
            libb = app.dependencies[0].dst

            self._check_node(libb, f"libb/{solution}#123", dependents=[app])
            self._check_node(app, "app/0.1", deps=[libb])

    def test_missing(self):
        # app -> libb[>0.1] (missing)
        consumer = self.recipe_consumer("app/0.1", ["libb/[>=0.0]"])

        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphMissingError

        self.assertEqual(1, len(deps_graph.nodes))
        app = deps_graph.root
        self._check_node(app, "app/0.1", deps=[])

    def test_userchannel_no_match(self):
        # app -> libb[>0.1] (missing)
        self.recipe_cache("libb/0.1@user/channel")
        consumer = self.recipe_consumer("app/0.1", ["libb/[>=0.0]"])

        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphMissingError

        self.assertEqual(1, len(deps_graph.nodes))
        app = deps_graph.root

        self._check_node(app, "app/0.1", deps=[])

    def test_required_userchannel_no_match(self):
        # app -> libb[>0.1] (missing)
        self.recipe_cache("libb/0.1")
        consumer = self.recipe_consumer("app/0.1", ["libb/[>=0.0]@user/channel"])

        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphMissingError

        self.assertEqual(1, len(deps_graph.nodes))
        app = deps_graph.root

        self._check_node(app, "app/0.1", deps=[])

    def test_transitive_out_range(self):
        # app -> libb[>0.1] (missing)
        self.recipe_cache("libb/0.1")
        consumer = self.recipe_consumer("app/0.1", ["libb/[>1.0]"])

        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphMissingError

        self.assertEqual(1, len(deps_graph.nodes))
        app = deps_graph.root

        self._check_node(app, "app/0.1", deps=[])


class TestVersionRangesDiamond(GraphManagerTest):
    def test_transitive(self):
        # app -> libb/0.1 -(range >0)-> liba/0.2
        #   \ -> libc/0.1 -(range <1)---/
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

        self._check_node(liba, "liba/0.2#123", dependents=[libb, libc], deps=[])
        self._check_node(libb, "libb/0.1#123", dependents=[app], deps=[liba])
        self._check_node(libc, "libc/0.1#123", dependents=[app], deps=[liba])
        self._check_node(app, "app/0.1", deps=[libb, libc])

    def test_transitive_interval(self):
        # app -> libb/0.1 -(range >0 <0.3)-> liba/0.2
        #   \ -> libc/0.1 -(range <1)--------/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("liba/0.3")
        self.recipe_cache("libb/0.1", ["liba/[>=0.0 <0.3]"])
        self.recipe_cache("libc/0.1", ["liba/[<1.0]"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        self._check_node(liba, "liba/0.2#123", dependents=[libb, libc], deps=[])
        self._check_node(libb, "libb/0.1#123", dependents=[app], deps=[liba])
        self._check_node(libc, "libc/0.1#123", dependents=[app], deps=[liba])
        self._check_node(app, "app/0.1", deps=[libb, libc])

    def test_transitive_fixed(self):
        # app -> libb/0.1 --------> liba/0.1
        #   \ -> libc/0.1 -(range <1)---/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        self.recipe_cache("libc/0.1", ["liba/[<1.0]"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        self._check_node(liba, "liba/0.1#123", dependents=[libb, libc], deps=[])
        self._check_node(libb, "libb/0.1#123", dependents=[app], deps=[liba])
        self._check_node(libc, "libc/0.1#123", dependents=[app], deps=[liba])
        self._check_node(app, "app/0.1", deps=[libb, libc])

    def test_transitive_conflict(self):
        # app -> libb/0.1 -(range >0)-> liba/0.2
        #   \ -> libc/0.1 -(range >1)---/
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/[>=0.0]"])
        self.recipe_cache("libc/0.1", ["liba/[>1.0]"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])
        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphConflictError

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        app.enabled_remotes = [Remote("foo", None)]
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        self._check_node(libb, "libb/0.1#123", dependents=[app], deps=[liba])
        self._check_node(libb, "libb/0.1#123", dependents=[app], deps=[liba])
        self._check_node(libc, "libc/0.1#123", dependents=[app], deps=[])
        self._check_node(app, "app/0.1", deps=[libb, libc])

    def test_transitive_fixed_conflict(self):
        # app -> libb/0.1 ---------> liba/0.2
        #   \ -> libc/0.1 -(range >1)---/
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/[>=0.0]"])
        self.recipe_cache("libc/0.1", ["liba/[>1.0]"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "libc/0.1"])
        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphConflictError

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        self._check_node(libb, "libb/0.1#123", dependents=[app], deps=[liba])
        self._check_node(libb, "libb/0.1#123", dependents=[app], deps=[liba])
        self._check_node(libc, "libc/0.1#123", dependents=[app], deps=[])
        self._check_node(app, "app/0.1", deps=[libb, libc])


class TestVersionRangesOverridesDiamond(GraphManagerTest):
    def test_transitive(self):
        # app -> libb/0.1 -(range >0)-> liba/0.2
        #   \ ---------------------------/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/[>=0.0]"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "liba/0.2"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(liba, "liba/0.2#123", dependents=[libb, app], deps=[])
        self._check_node(libb, "libb/0.1#123", dependents=[app], deps=[liba])
        self._check_node(app, "app/0.1", deps=[libb, liba])

    def test_transitive_overriden(self):
        # app -> libb/0.1 -(range >0)-> liba/0.1
        #   \ ---------liba/0.1-------------/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/[>=0.0]"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "liba/0.1"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(liba, "liba/0.1#123", dependents=[libb, app], deps=[])
        self._check_node(libb, "libb/0.1#123", dependents=[app], deps=[liba])
        self._check_node(app, "app/0.1", deps=[libb, liba])

    def test_transitive_fixed(self):
        # app ---> libb/0.1 -----------> liba/0.1
        #   \ --------(range<1)----------/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "liba/[<1.0]"])
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(liba, "liba/0.1#123", dependents=[libb, app], deps=[])
        self._check_node(libb, "libb/0.1#123", dependents=[app], deps=[liba])
        self._check_node(app, "app/0.1", deps=[libb, liba])

    def test_transitive_fixed_conflict(self):
        # app ---> libb/0.1 -----------> liba/0.1
        #   \ --------(range>1)----------/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/1.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.recipe_consumer("app/0.1", ["libb/0.1", "liba/[>1.0]"])
        deps_graph = self.build_consumer(consumer, install=False)

        assert type(deps_graph.error) == GraphConflictError

        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst

    def test_transitive_fixed_conflict_forced(self):
        # app ---> libb/0.1 -----------> liba/1.2
        #   \ --------(range>1)----------/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/1.2")
        self.recipe_cache("libb/0.1", ["liba/0.1"])
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_require("libb/0.1")
                                           .with_requirement("liba/[>1.0]", force=True))
        deps_graph = self.build_consumer(consumer, install=False)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(liba, "liba/1.2#123", dependents=[libb, app], deps=[])
        self._check_node(libb, "libb/0.1#123", dependents=[app], deps=[liba])
        self._check_node(app, "app/0.1", deps=[libb, liba])

    def test_two_ranges_overriden(self):
        # app -> libb/0.1 -(range >0)-> liba/0.1
        #   \ ---------liba/[<0.3>]-------------/
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("liba/0.3")
        self.recipe_cache("libb/0.1", ["liba/[>=0.0]"])
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_require("libb/0.1")
                                           .with_requirement("liba/[<0.4]"))
        deps_graph = self.build_consumer(consumer)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(liba, "liba/0.3#123", dependents=[libb, app], deps=[])
        self._check_node(libb, "libb/0.1#123", dependents=[app], deps=[liba])
        self._check_node(app, "app/0.1", deps=[libb, liba])

    def test_two_ranges_overriden_no_conflict(self):
        # app -> libb/0.1 -(range >0)-> liba/0.1
        #   \ ---------liba/[<0.3>]-------------/
        # Conan learned to solve this conflict in 2.0.14
        self.recipe_cache("liba/0.1")
        self.recipe_cache("liba/0.2")
        self.recipe_cache("liba/0.3")
        self.recipe_cache("libb/0.1", ["liba/[>=0.0]"])
        consumer = self.consumer_conanfile(GenConanfile("app", "0.1").with_require("libb/0.1")
                                           .with_requirement("liba/[<0.3]"))
        deps_graph = self.build_consumer(consumer, install=False)

        # This is no longer a conflict, and Conan knows that liba/2.0 is a valid joint solution

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self._check_node(liba, "liba/0.2#123", dependents=[libb, app], deps=[])
        self._check_node(libb, "libb/0.1#123", dependents=[app], deps=[liba])
        self._check_node(app, "app/0.1", deps=[libb, liba])


def test_mixed_user_channel():
    # https://github.com/conan-io/conan/issues/7846
    t = TestClient(default_server_user=True, light=True)
    t.save({"conanfile.py": GenConanfile()})
    t.run("create . --name=pkg --version=1.0")
    t.run("create . --name=pkg --version=1.1")
    t.run("create . --name=pkg --version=2.0")
    t.run("create . --name=pkg --version=1.0 --user=user --channel=testing")
    t.run("create . --name=pkg --version=1.1 --user=user --channel=testing")
    t.run("create . --name=pkg --version=2.0 --user=user --channel=testing")
    t.run("upload * --confirm -r default")
    t.run("remove * -c")

    t.run('install --requires="pkg/[>0 <2]@"')
    t.assert_listed_require({"pkg/1.1": "Downloaded (default)"})
    t.run('install --requires="pkg/[>0 <2]@user/testing"')
    t.assert_listed_require({"pkg/1.1@user/testing": "Downloaded (default)"})


def test_remote_version_ranges():
    t = TestClient(default_server_user=True, light=True)
    t.save({"conanfile.py": GenConanfile()})
    for v in ["0.1", "0.2", "0.3", "1.1", "1.1.2", "1.2.1", "2.1", "2.2.1"]:
        t.run(f"create . --name=dep --version={v}")
    t.run("upload * --confirm -r default")
    # TODO: Deprecate the comma separator for expressions
    for expr, solution in [(">0.0", "2.2.1"),
                           (">0.1 <1", "0.3"),
                           (">0.1 <1||2.1", "2.1"),
                           ("", "2.2.1"),
                           ("~0", "0.3"),
                           ("~1", "1.2.1"),
                           ("~1.1", "1.1.2"),
                           ("~2", "2.2.1"),
                           ("~2.1", "2.1"),
                           ]:
        t.run("remove * -c")
        t.save({"conanfile.py": GenConanfile().with_requires(f"dep/[{expr}]")})
        t.run("install .")
        assert str(t.out).count("Not found in local cache, looking in remotes") == 1
        t.assert_listed_binary({f"dep/{solution}": ("da39a3ee5e6b4b0d3255bfef95601890afd80709",
                                                    "Download (default)")})


def test_different_user_channel_resolved_correctly():
    server1 = TestServer()
    server2 = TestServer()
    servers = OrderedDict([("server1", server1), ("server2", server2)])

    client = TestClient(servers=servers, inputs=2*["admin", "password"], light=True)
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=lib --version=1.0 --user=conan --channel=stable")
    client.run("create . --name=lib --version=1.0 --user=conan --channel=testing")
    client.run("upload lib/1.0@conan/stable -r=server1")
    client.run("upload lib/1.0@conan/testing -r=server2")

    client2 = TestClient(servers=servers, light=True)
    client2.run("install --requires=lib/[>=1.0]@conan/testing")
    assert f"lib/1.0@conan/testing: Retrieving package {NO_SETTINGS_PACKAGE_ID} " \
           f"from remote 'server2' " in client2.out


def test_unknown_options():
    c = TestClient(light=True)
    c.save({"conanfile.py": GenConanfile("lib", "2.0")})
    c.run("create .")

    c.run("graph info --requires=lib/[>1.2,<1.4]", assert_error=True)
    assert '"<1.4" in version range ">1.2,<1.4" is not a valid option' in c.out

    c.run("graph info --requires=lib/[>1.2,unknown_conf]")
    assert 'WARN: Unrecognized version range option "unknown_conf" in ">1.2,unknown_conf"' in c.out


@pytest.mark.parametrize("version_range,should_warn", [
    [">=0.1, include_prereleases", False],
    [">=0.1, include_prerelease=True", True],
    [">=0.1, include_prerelease=False", True]
])
def test_bad_options_syntax(version_range, should_warn):
    """We don't error out on bad options, maybe we should,
    but for now this test ensures we don't change it without realizing"""
    tc = TestClient(light=True)
    tc.save({"lib/conanfile.py": GenConanfile("lib", "1.0"),
             "app/conanfile.py": GenConanfile("app", "1.0").with_requires(f"lib/[{version_range}]")})
    tc.run("export lib")
    tc.run("graph info app/conanfile.py")
    if should_warn:
        assert "its presence unconditionally enables prereleases" in tc.out
    else:
        assert "its presence unconditionally enables prereleases" not in tc.out
