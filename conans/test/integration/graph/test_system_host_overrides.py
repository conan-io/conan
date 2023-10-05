from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class TestSystemHostOverrides:
    def test_system_tool_require(self):
        c = TestClient()
        c.save({"dep2/conanfile.py": GenConanfile("dep2"),
                "pkg/conanfile.py": GenConanfile().with_requires("dep1/1.0", "dep2/[>=1.0 <2]"),
                "profile": "[system_deps]\ndep1/1.0\ndep2/1.1: dep2/1.1@system"})
        c.run("create dep2 --version=1.1 --user=system")
        rrev = c.exported_recipe_revision()
        c.run("install pkg -pr=profile")
        c.assert_listed_require({"dep1/1.0": "System tool",
                                 f"dep2/1.1@system#{rrev}": "Cache"})

        # Check lockfile
        c.run("lock create pkg -pr=profile")
        lock = c.load("pkg/conan.lock")
        print(lock)
        assert f"dep2/1.1@system#{rrev}" in lock
        assert "dep1/1.0" in lock

        c.run("create dep2 --version=1.2")
        # with lockfile
        c.run("install pkg -pr=profile")
        c.assert_listed_require({"dep1/1.0": "System tool",
                                 f"dep2/1.1@system#{rrev}": "Cache"})
