import json
import time

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


class TestLRU:
    def test_error_lru_remote(self):
        c = TestClient(default_server_user=True)
        c.run("list * --lru=1s -r=default", assert_error=True)
        assert "'--lru' cannot be used in remotes, only in cache" in c.out

    @pytest.mark.parametrize("method", ["list", "remove"])
    def test_cache_clean_lru(self, method):
        c = TestClient()
        c.save({"conanfile.py": GenConanfile()})
        c.run("create . --name=pkg --version=0.1")
        c.run("create . --name=dep --version=0.2")

        time.sleep(2)
        # This should update the LRU
        c.run("install --requires=pkg/0.1")
        # Removing recipes (+ its binaries) that recipes haven't been used
        if method == "list":
            c.run("list *#* --lru=1s --format=json", redirect_stdout="old.json")
            c.run("remove --list=old.json -c")
        else:
            c.run("remove * --lru=1s -c")
        # Do the checks
        c.run("list *:*#*")
        assert "pkg" in c.out
        assert "da39a3ee5e6b4b0d3255bfef95601890afd80709" in c.out
        assert "dep" not in c.out

        time.sleep(2)
        # This should update the LRU of the recipe only
        c.run("graph info --requires=pkg/0.1")
        # IMPORTANT: Note the pattern is NOT the same as the equivalent for 'conan remove'
        if method == "list":
            c.run("list *#*:*#* --lru=1s --format=json", redirect_stdout="old.json")
            c.run("remove --list=old.json -c")
        else:
            c.run("remove *:* --lru=1s -c")

        # Check the binary has been removed, but the recipe is still there
        c.run("list *:*")

        assert "pkg" in c.out
        assert "da39a3ee5e6b4b0d3255bfef95601890afd80709" not in c.out
        assert "dep" not in c.out

    def test_update_lru_when_used_as_dependency(self):
        """Show that using a recipe as a dependency will update its LRU"""
        c = TestClient()
        c.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
                "conanfile.py": GenConanfile("app", "1.0").with_require("dep/1.0")})

        c.run("create dep")
        time.sleep(2)
        c.run("create .")
        # Dep is not removed because its lru was updated as part of the above create
        c.run("remove * --lru=1s -c -f=json", redirect_stdout="removed.json")
        removed = json.loads(c.load("removed.json"))
        assert len(removed["Local Cache"]) == 0
