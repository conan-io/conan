import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_conanfile_txt_deps_ranges():
    creator = TestClient()
    client = TestClient(cache_folder=creator.cache_folder)

    creator.save({"conanfile.py": GenConanfile()})
    creator.run("create . pkg/0.1@user/testing")

    client.save({"conanfile.txt": "[requires]\npkg/[>0.0]@user/testing"})
    client.run("lock create conanfile.txt --base --lockfile-out=conan.lock")
    assert "pkg/0.1@user/testing from local cache - Cache" in client.out

    creator.run("create . pkg/0.2@user/testing")

    client.run("install . --lockfile=conan.lock")
    assert "pkg/0.1@user/testing from local cache - Cache" in client.out
    assert "pkg/0.2" not in client.out
    client.run("install .")
    assert "pkg/0.2@user/testing from local cache - Cache" in client.out
    assert "pkg/0.1" not in client.out


def test_conanfile_txt_deps_ranges_transitive():
    creator = TestClient()
    client = TestClient(cache_folder=creator.cache_folder)

    creator.save({"dep/conanfile.py": GenConanfile(),
                  "pkg/conanfile.py": GenConanfile().with_requires("dep/[>0.0]@user/testing")})
    creator.run("create dep dep/0.1@user/testing")
    creator.run("create pkg pkg/0.1@user/testing")

    client.save({"conanfile.txt": "[requires]\npkg/[>0.0]@user/testing"})
    client.run("lock create conanfile.txt --base --lockfile-out=conan.lock")
    assert "dep/0.1@user/testing from local cache - Cache" in client.out
    assert "pkg/0.1@user/testing from local cache - Cache" in client.out

    creator.run("create dep dep/0.2@user/testing")

    client.run("install . --lockfile=conan.lock")
    assert "dep/0.1@user/testing from local cache - Cache" in client.out
    assert "dep/0.2" not in client.out
    client.run("install .", assert_error=True)
    assert "dep/0.2@user/testing from local cache - Cache" in client.out
    assert "dep/0.1" not in client.out


def test_conditional():
    creator = TestClient()
    client = TestClient(cache_folder=creator.cache_folder)

    pkg_conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def requirements(self):
                if self.settings.os == "Windows":
                    self.requires("windep/[>0.0]")
                else:
                    self.requires("nixdep/[>0.0]")
        """)
    creator.save({"dep/conanfile.py": GenConanfile(),
                  "pkg/conanfile.py": pkg_conanfile})
    creator.run("create dep windep/0.1@")
    creator.run("create dep nixdep/0.1@")

    creator.run("create pkg pkg/0.1@ -s os=Windows")
    creator.run("create pkg pkg/0.1@ -s os=Linux")

    client.save({"conanfile.txt": "[requires]\npkg/0.1"})
    client.run("lock create conanfile.txt --base --lockfile-out=conan.lock -s os=Windows")
    assert "windep/0.1 from local cache - Cache" in client.out
    assert "pkg/0.1 from local cache - Cache" in client.out
    client.run("lock create conanfile.txt --base --lockfile=conan.lock "
               "--lockfile-out=conan.lock -s os=Linux")
    assert "nixdep/0.1 from local cache - Cache" in client.out
    assert "pkg/0.1 from local cache - Cache" in client.out

    creator.run("create dep windep/0.2@")
    creator.run("create dep nixdep/0.2@")

    client.run("install . --lockfile=conan.lock --lockfile-out=win.lock -s os=Windows")
    assert "windep/0.1 from local cache - Cache" in client.out
    assert "windep/0.2" not in client.out
    client.run("install . -s os=Windows", assert_error=True)
    assert "windep/0.2 from local cache - Cache" in client.out
    assert "windep/0.1" not in client.out

    client.run("install . --lockfile=conan.lock --lockfile-out=linux.lock -s os=Linux")
    assert "nixdep/0.1 from local cache - Cache" in client.out
    assert "nixdep/0.2" not in client.out
    client.run("install . -s os=Linux", assert_error=True)
    assert "nixdep/0.2 from local cache - Cache" in client.out
    assert "nixdep/0.1" not in client.out


def test_lock_full_config():
    creator = TestClient()
    client = TestClient(cache_folder=creator.cache_folder)

    creator.save({"dep/conanfile.py": GenConanfile().with_settings("os"),
                  "pkg/conanfile.py": GenConanfile().with_settings("os").with_requires("dep/0.1")})
    creator.run("create dep dep/0.1@ -s os=Linux")
    creator.run("create pkg pkg/0.1@ -s os=Linux")

    client.save({"conanfile.txt": "[requires]\npkg/0.1"})
    client.run("lock create conanfile.txt --lockfile-out=conan.lock -s os=Linux")
    assert "dep/0.1 from local cache - Cache" in client.out
    assert "pkg/0.1 from local cache - Cache" in client.out

    creator.run("create dep dep/0.2@ -s os=Linux")

    client.run("install . --lockfile=conan.lock")
    assert "Linux" in client.out
    assert "dep/0.1 from local cache - Cache" in client.out
    assert "dep/0.2" not in client.out
