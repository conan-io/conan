import time

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class TestLRU:
    def test_error_lru_remote(self):
        c = TestClient(default_server_user=True)
        c.run("list * --lru=1s -r=default", assert_error=True)
        assert "'--lru' cannot be used in remotes, only in cache" in c.out

    def test_cache_clean_lru(self):
        c = TestClient()
        c.save({"conanfile.py": GenConanfile()})
        c.run("create . --name=pkg --version=0.1")
        c.run("create . --name=dep --version=0.2")

        time.sleep(2)
        # This should update the LRU
        c.run("install --requires=pkg/0.1")
        c.run("list *#* --lru=1s --format=json", redirect_stdout="old.json")
        c.run("remove --list=old.json -c")
        # Do the checks
        c.run("list *:*#*")
        assert "pkg" in c.out
        assert "da39a3ee5e6b4b0d3255bfef95601890afd80709" in c.out
        assert "dep" not in c.out

        time.sleep(2)
        # This should update the LRU of the recipe only
        c.run("graph info --requires=pkg/0.1")
        # IMPORTANT: Note the pattern is NOT the same as the equivalent for 'conan remove'
        c.run("list *#*:*#* --lru=1s --format=json", redirect_stdout="old.json")
        c.run("remove --list=old.json -c")

        # Check the binary has been removed, but the recipe is still there
        c.run("list *:*")

        assert "pkg" in c.out
        assert "da39a3ee5e6b4b0d3255bfef95601890afd80709" not in c.out
        assert "dep" not in c.out
