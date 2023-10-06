from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class TestSystemHostOverrides:
    def test_system_dep(self):
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
        assert f"dep2/1.1@system#{rrev}" in lock
        assert "dep1/1.0" in lock

        c.run("create dep2 --version=1.2")
        # with lockfile
        c.run("install pkg -pr=profile")
        c.assert_listed_require({"dep1/1.0": "System tool",
                                 f"dep2/1.1@system#{rrev}": "Cache"})

    def test_system_dep_diamond(self):
        c = TestClient()
        c.save({"liba/conanfile.py": GenConanfile("liba"),
                "libb/conanfile.py": GenConanfile("libb", "0.1").with_requires("liba/[>=1.0 <2]"),
                "libc/conanfile.py": GenConanfile("libc", "0.1").with_requires("liba/[>=1.2 <1.9]"),
                "app/conanfile.py": GenConanfile().with_requires("libb/0.1", "libc/0.1"),
                "profile": "[system_deps]\nliba/1.2: liba/1.2@system"})
        c.run("create liba --version=1.2")
        rrev = c.exported_recipe_revision()
        c.run("create liba --version=1.2 --user=system")
        c.run("create libb")
        c.run("create libc")

        c.run("install app -pr=profile", assert_error=True)
        assert "ERROR: Missing binary: libb/0.1:51c3851513513116ae68e07a0fad83a04a80d62a" in c.out
        assert "ERROR: Missing binary: libc/0.1:51c3851513513116ae68e07a0fad83a04a80d62a" in c.out

        c.run("install app -pr=profile --build=missing")
        c.assert_listed_require({f"liba/1.2@system#{rrev}": "Cache"})

        # Check lockfile
        c.run("lock create app -pr=profile")
        lock = c.load("app/conan.lock")
        assert f"liba/1.2@system#{rrev}" in lock

        c.run("create liba --version=1.3")
        # with lockfile
        c.run("install app -pr=profile")
        c.assert_listed_require({f"liba/1.2@system#{rrev}": "Cache"})

    def test_replace_zlib_zlibng_error(self):
        c = TestClient()
        c.save({"zlibng/conanfile.py": GenConanfile("zlibng"),
                "pkg/conanfile.py": GenConanfile().with_requires("zlib/1.2.11"),
                "profile": "[system_deps]\nzlib/1.2.11: zlibng/1.2.11"})
        c.run("create zlibng --version=1.2.11")
        rrev = c.exported_recipe_revision()
        c.run("install pkg -pr=profile", assert_error=True)
        assert "[system_deps] zlibng/1.2.11 cannot replace package name" in c.out
