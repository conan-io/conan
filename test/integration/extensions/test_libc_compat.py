import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.fixture()
def client():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os"

            def package_info(self):
                self.output.info(f"PackageInfo!: libc: {self.settings.get_safe('os.libc')} "
                                 f"{self.settings.get_safe('os.libc.version')}!")
        """)
    c.save({"conanfile.py": conanfile,
            "consumer/conanfile.py": GenConanfile().with_require("pkg/0.1")})
    return c


def test_compatible_older_libc_version(client):
    c = client
    c.run("create . -s os=Linux -s os.libc=glibc -s os.libc.version=2.28")
    c.run("install consumer -s os=Linux -s os.libc=glibc -s os.libc.version=2.35")
    assert "pkg/0.1: PackageInfo!: libc: glibc 2.28!" in c.out
    assert "pkg/0.1: Found compatible package" in c.out


def test_compatible_closest_libc_version_first(client):
    c = client
    c.run("create . -s os=Linux -s os.libc=glibc -s os.libc.version=2.17")
    c.run("create . -s os=Linux -s os.libc=glibc -s os.libc.version=2.31")
    c.run("create . -s os=Linux")
    c.run("install consumer -s os=Linux -s os.libc=glibc -s os.libc.version=2.35")
    assert "pkg/0.1: PackageInfo!: libc: glibc 2.31!" in c.out


def test_incompatible_newer_libc_version(client):
    c = client
    c.run("create . -s os=Linux -s os.libc=glibc -s os.libc.version=2.39")
    c.run("install consumer -s os=Linux -s os.libc=glibc -s os.libc.version=2.35",
          assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/0.1'" in c.out


def test_incompatible_different_libc(client):
    c = client
    c.run("create . -s os=Linux -s os.libc=musl -s os.libc.version=1.2.4")
    c.run("install consumer -s os=Linux -s os.libc=glibc -s os.libc.version=2.35",
          assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/0.1'" in c.out
    c.run("create . -s os=Linux -s os.libc=glibc -s os.libc.version=2.17")
    c.run("install consumer -s os=Linux -s os.libc=musl -s os.libc.version=1.2.3",
          assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/0.1'" in c.out


@pytest.mark.parametrize("package_settings", ["", "-s os.libc=glibc"])
def test_compatible_libc_unset(client, package_settings):
    c = client
    c.run(f"create . -s os=Linux {package_settings}")
    package_id = c.created_package_id("pkg/0.1")
    c.run("install consumer -s os=Linux -s os.libc=glibc -s os.libc.version=2.35")
    assert f"pkg/0.1: Found compatible package '{package_id}'" in c.out
    c.assert_listed_binary({"pkg/0.1": (package_id, "Cache")})


def test_compatible_libc_unset_disabled(client):
    c = client
    c.run("create . -s os=Linux")
    c.run("install consumer -s os=Linux -s os.libc=glibc -s os.libc.version=2.35 "
          "-c tools.graph:compatibility_libc_unset=False", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/0.1'" in c.out
    # Older libc versions are still compatible
    c.run("create . -s os=Linux -s os.libc=glibc -s os.libc.version=2.28")
    c.run("install consumer -s os=Linux -s os.libc=glibc -s os.libc.version=2.35 "
          "-c tools.graph:compatibility_libc_unset=False")
    assert "pkg/0.1: PackageInfo!: libc: glibc 2.28!" in c.out


def test_compatible_libc_unset_disabled_per_package(client):
    c = client
    c.run("create . -s os=Linux")
    c.run("install consumer -s os=Linux -s os.libc=glibc -s os.libc.version=2.35 "
          "-c pkg/*:tools.graph:compatibility_libc_unset=False", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/0.1'" in c.out


def test_compatibility_libc_extension_properties():
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            settings = "os"
            extension_properties = {"compatibility_libc": False}
        """)
    c.save({"conanfile.py": conanfile,
            "consumer/conanfile.py": GenConanfile().with_require("pkg/0.1")})
    c.run("create . -s os=Linux -s os.libc=glibc -s os.libc.version=2.28")
    c.run("create . -s os=Linux")
    c.run("install consumer -s os=Linux -s os.libc=glibc -s os.libc.version=2.35",
          assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/0.1'" in c.out


def test_compatible_libc_and_cppstd():
    c = TestClient()
    profile = textwrap.dedent("""
        [settings]
        os=Linux
        os.libc=glibc
        compiler=gcc
        compiler.version=12
        compiler.libcxx=libstdc++
        """)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_settings("os", "compiler"),
            "consumer/conanfile.py": GenConanfile().with_require("pkg/0.1"),
            "myprofile": profile})
    c.run("create . -pr=myprofile -s os.libc.version=2.28 -s compiler.cppstd=17")
    c.run("install consumer -pr=myprofile -s os.libc.version=2.35 -s compiler.cppstd=20")
    assert "pkg/0.1: Found compatible package" in c.out
    assert "compiler.cppstd=17" in c.out
    assert "os.libc.version=2.28" in c.out


def test_consumer_libc_unset_most_portable_first(client):
    c = client
    c.run("create . -s os=Linux -s os.libc=glibc -s os.libc.version=2.31")
    c.run("create . -s os=Linux -s os.libc=glibc -s os.libc.version=2.17")
    c.run("install consumer -s os=Linux")
    assert "pkg/0.1: PackageInfo!: libc: glibc 2.17!" in c.out


@pytest.mark.parametrize("package_settings", ["-s os.libc=glibc -s os.libc.version=2.39",
                                              "-s os.libc=glibc"])
def test_consumer_libc_unset(client, package_settings):
    c = client
    c.run(f"create . -s os=Linux {package_settings}")
    package_id = c.created_package_id("pkg/0.1")
    c.run("install consumer -s os=Linux")
    assert f"pkg/0.1: Found compatible package '{package_id}'" in c.out
    c.assert_listed_binary({"pkg/0.1": (package_id, "Cache")})


def test_consumer_libc_version_unset(client):
    c = client
    c.run("create . -s os=Linux -s os.libc=musl -s os.libc.version=1.2.5")
    c.run("create . -s os=Linux -s os.libc=musl -s os.libc.version=1.2.3")
    c.run("install consumer -s os=Linux -s os.libc=musl")
    assert "pkg/0.1: PackageInfo!: libc: musl 1.2.3!" in c.out


def test_consumer_libc_unset_not_musl(client):
    c = client
    c.run("create . -s os=Linux -s os.libc=musl -s os.libc.version=1.2.5")
    c.run("install consumer -s os=Linux", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/0.1'" in c.out


def test_consumer_libc_unset_disabled(client):
    c = client
    c.run("create . -s os=Linux -s os.libc=glibc -s os.libc.version=2.28")
    c.run("install consumer -s os=Linux -c tools.graph:compatibility_libc_unset=False",
          assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/0.1'" in c.out


def test_consumer_libc_unset_not_linux(client):
    c = client
    c.run("create . -s os=Windows")
    c.run("install consumer -s os=Windows")
    assert "compatible configurations" not in c.out


def test_settings_without_libc():
    c = TestClient(light=True)  # settings.yml without os.libc
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_settings("os")})
    c.run("create . -s os=Windows")
    c.run("install --requires=pkg/0.1 -s os=Linux", assert_error=True)
    assert "ERROR: Missing prebuilt package for 'pkg/0.1'" in c.out
