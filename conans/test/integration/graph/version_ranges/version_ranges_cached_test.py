from collections import OrderedDict

import pytest
from mock import patch

from conans.client.remote_manager import RemoteManager
from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer


class TestVersionRangesCache:

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.counters = {"server0": 0, "server1": 0}

    def _mocked_search_recipes(self, remote, pattern, ignorecase=True):
        packages = {
            "server0": [RecipeReference.loads("liba/1.0.0"),
                        RecipeReference.loads("liba/1.1.0")],
            "server1": [RecipeReference.loads("liba/2.0.0"),
                        RecipeReference.loads("liba/2.1.0")]
        }
        self.counters[remote.name] = self.counters[remote.name] + 1
        return packages[remote.name]

    def test_version_ranges_cached(self):
        servers = OrderedDict()
        for index in range(2):
            servers[f"server{index}"] = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")],
                                                   users={"user": "password"})

        users = {"server0": [("user", "password")],
                 "server1": [("user", "password")]}

        client = TestClient(servers=servers, inputs=["user", "password", "user", "password"])

        # server0 does not satisfy range
        # server1 does

        for minor in range(2):
            client.save({"conanfile.py": GenConanfile("liba", f"1.{minor}.0")})
            client.run("create .")
            client.run(f"upload liba/1.{minor}.0 -r server0 -c")

        for minor in range(2):
            client.save({"conanfile.py": GenConanfile("liba", f"2.{minor}.0")})
            client.run("create .")
            client.run(f"upload liba/2.{minor}.0 -r server1 -c")

        client.run("remove * -f")

        client.save({"conanfile.py": GenConanfile("libb", "1.0").with_require("liba/[>=2.0]")})
        client.run("create .")

        client.save({"conanfile.py": GenConanfile("libc", "1.0").with_require("liba/[>=2.0]")})
        client.run("create .")

        client.save({"conanfile.py": GenConanfile("consumer", "1.0")
                    .with_requires("libb/1.0", "libc/1.0")})

        # should call only once to server0
        self.counters["server0"] = 0
        self.counters["server1"] = 0
        with patch.object(RemoteManager, "search_recipes", new=self._mocked_search_recipes):
            client.run("create . --update")
            assert self.counters["server0"] == 1
            assert self.counters["server1"] == 1
