import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_conanfile_txt_deps_ranges():
    client = TestClient()
    client.save({"pkg/conanfile.py": GenConanfile(),
                 "consumer/conanfile.txt": "[requires]\npkg/[>0.0]@user/testing"})
    client.run("create pkg pkg/0.1@user/testing")
    client.run("lock create consumer/conanfile.txt --base --lockfile-out=conan.lock")
    assert "pkg/0.1@user/testing from local cache - Cache" in client.out

    client.run("create pkg pkg/0.2@user/testing")

    client.run("install consumer/conanfile.txt --lockfile=conan.lock")
    assert "pkg/0.1@user/testing from local cache - Cache" in client.out
    assert "pkg/0.2" not in client.out
    client.run("install consumer/conanfile.txt")
    assert "pkg/0.2@user/testing from local cache - Cache" in client.out
    assert "pkg/0.1" not in client.out


def test_conanfile_txt_deps_ranges_transitive():
    client = TestClient()
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": GenConanfile().with_requires("dep/[>0.0]@user/testing"),
                 "consumer/conanfile.txt": "[requires]\npkg/[>0.0]@user/testing"})
    client.run("create dep dep/0.1@user/testing")
    client.run("create pkg pkg/0.1@user/testing")

    client.run("lock create consumer/conanfile.txt --base --lockfile-out=conan.lock")
    assert "dep/0.1@user/testing from local cache - Cache" in client.out
    assert "pkg/0.1@user/testing from local cache - Cache" in client.out

    client.run("create dep dep/0.2@user/testing")

    client.run("install consumer/conanfile.txt --lockfile=conan.lock")
    assert "dep/0.1@user/testing from local cache - Cache" in client.out
    assert "dep/0.2" not in client.out
    client.run("install consumer/conanfile.txt", assert_error=True)
    assert "dep/0.2@user/testing from local cache - Cache" in client.out
    assert "dep/0.1" not in client.out


def test_conditional_os():
    client = TestClient()

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
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": pkg_conanfile,
                 "consumer/conanfile.txt": "[requires]\npkg/0.1"})
    client.run("create dep windep/0.1@")
    client.run("create dep nixdep/0.1@")

    client.run("create pkg pkg/0.1@ -s os=Windows")
    client.run("create pkg pkg/0.1@ -s os=Linux")

    client.run("lock create consumer/conanfile.txt --base --lockfile-out=conan.lock -s os=Windows")
    assert "windep/0.1 from local cache - Cache" in client.out
    assert "pkg/0.1 from local cache - Cache" in client.out
    client.run("lock create consumer/conanfile.txt --base --lockfile=conan.lock "
               "--lockfile-out=conan.lock -s os=Linux")
    assert "nixdep/0.1 from local cache - Cache" in client.out
    assert "pkg/0.1 from local cache - Cache" in client.out

    client.run("create dep windep/0.2@")
    client.run("create dep nixdep/0.2@")

    client.run("install consumer --lockfile=conan.lock --lockfile-out=win.lock -s os=Windows")
    assert "windep/0.1 from local cache - Cache" in client.out
    assert "windep/0.2" not in client.out
    client.run("install consumer -s os=Windows", assert_error=True)
    assert "windep/0.2 from local cache - Cache" in client.out
    assert "windep/0.1" not in client.out

    client.run("install consumer --lockfile=conan.lock --lockfile-out=linux.lock -s os=Linux")
    assert "nixdep/0.1 from local cache - Cache" in client.out
    assert "nixdep/0.2" not in client.out
    client.run("install consumer -s os=Linux", assert_error=True)
    assert "nixdep/0.2 from local cache - Cache" in client.out
    assert "nixdep/0.1" not in client.out


def test_conditional_same_package():
    # What happens when a conditional requires different versions of the same package?
    client = TestClient()

    pkg_conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def requirements(self):
                if self.settings.os == "Windows":
                    self.requires("dep/0.1")
                else:
                    self.requires("dep/0.2")
        """)
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": pkg_conanfile,
                 "consumer/conanfile.txt": "[requires]\npkg/0.1"})
    client.run("create dep dep/0.1@")
    client.run("create dep dep/0.2@")

    client.run("create pkg pkg/0.1@ -s os=Windows")
    client.run("create pkg pkg/0.1@ -s os=Linux")

    client.run("lock create consumer/conanfile.txt --base --lockfile-out=conan.lock -s os=Windows")
    assert "dep/0.1 from local cache - Cache" in client.out
    assert "dep/0.2" not in client.out
    client.run("lock create consumer/conanfile.txt --base --lockfile=conan.lock "
               "--lockfile-out=conan.lock -s os=Linux")
    assert "dep/0.2 from local cache - Cache" in client.out
    assert "dep/0.1" not in client.out

    client.run("install consumer --lockfile=conan.lock --lockfile-out=win.lock -s os=Windows")
    assert "dep/0.1 from local cache - Cache" in client.out
    assert "dep/0.2" not in client.out

    client.run("install consumer --lockfile=conan.lock --lockfile-out=linux.lock -s os=Linux")
    assert "dep/0.2 from local cache - Cache" in client.out
    assert "dep/0.1" not in client.out


def test_conditional_incompatible_range():
    client = TestClient()

    pkg_conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def requirements(self):
                if self.settings.os == "Windows":
                    self.requires("dep/[<1.0]")
                else:
                    self.requires("dep/[>=1.0]")
        """)
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": pkg_conanfile,
                 "consumer/conanfile.txt": "[requires]\npkg/0.1"})
    client.run("create dep dep/0.1@")
    client.run("create dep dep/1.1@")

    client.run("create pkg pkg/0.1@ -s os=Windows")
    client.run("create pkg pkg/0.1@ -s os=Linux")

    client.run("lock create consumer/conanfile.txt --base --lockfile-out=conan.lock -s os=Windows")
    assert "dep/0.1 from local cache - Cache" in client.out
    assert "dep/1.1" not in client.out
    client.run("lock create consumer/conanfile.txt --base --lockfile=conan.lock "
               "--lockfile-out=conan.lock -s os=Linux")
    assert "dep/1.1 from local cache - Cache" in client.out
    assert "dep/0.1" not in client.out

    client.run("install consumer --lockfile=conan.lock --lockfile-out=win.lock -s os=Windows")
    assert "dep/0.1 from local cache - Cache" in client.out
    assert "dep/1.1" not in client.out

    client.run("install consumer --lockfile=conan.lock --lockfile-out=linux.lock -s os=Linux")
    assert "dep/1.1 from local cache - Cache" in client.out
    assert "dep/0.1" not in client.out


def test_conditional_compatible_range():
    client = TestClient()

    pkg_conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            settings = "os"
            def requirements(self):
                if self.settings.os == "Windows":
                    self.requires("dep/[<0.2]")
                else:
                    self.requires("dep/[>0.0]")
        """)
    client.save({"dep/conanfile.py": GenConanfile(),
                 "pkg/conanfile.py": pkg_conanfile,
                 "consumer/conanfile.txt": "[requires]\npkg/0.1"})
    client.run("create dep dep/0.1@")
    client.run("create dep dep/0.2@")

    client.run("create pkg pkg/0.1@ -s os=Windows")
    client.run("create pkg pkg/0.1@ -s os=Linux")

    client.run("lock create consumer/conanfile.txt --base --lockfile-out=conan.lock -s os=Linux")
    assert "dep/0.2 from local cache - Cache" in client.out
    assert "dep/0.1" not in client.out
    print("WINDOWS-------------------------------------------")
    print(client.out)
    print(client.load("conan.lock"))
    client.run("lock create consumer/conanfile.txt --base --lockfile=conan.lock "
               "--lockfile-out=conan.lock -s os=Windows")
    assert "dep/0.1 from local cache - Cache" in client.out
    assert "dep/0.2" not in client.out
    print("Linux-------------------------------------------")
    print(client.out)
    print(client.load("conan.lock"))

    client.run("install consumer --lockfile=conan.lock --lockfile-out=win.lock -s os=Windows")
    assert "dep/0.1 from local cache - Cache" in client.out
    assert "dep/0.2" not in client.out

    client.run("install consumer --lockfile=conan.lock --lockfile-out=linux.lock -s os=Linux "
               "--build=missing")
    print("Install LINUX-------------------------------------------")
    print(client.out)
    assert "dep/0.2 from local cache - Cache" in client.out
    assert "dep/0.1" not in client.out


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
