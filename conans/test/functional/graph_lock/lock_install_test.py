import pytest

from conans.test.utils.tools import TestClient, GenConanfile


@pytest.mark.xfail(reason="lockfiles do not work temporarily with new graph, needs to be recovered")
def test_install():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("pkga", "0.1").with_package_file("file.h", "0.1")})
    client.run("create . --user=user --channel=channel")

    # Use a consumer with a version range
    client.save({"conanfile.py":
                 GenConanfile("pkgb", "0.1").with_require("pkga/[>=0.1]@user/channel")})
    client.run("create . --user=user --channel=channel")
    client.run("lock create --requires=pkgb/0.1@user/channel --lockfile-out=lock1.lock")

    # We can create a pkga/0.2, but it will not be used
    client.save({"conanfile.py": GenConanfile("pkga", "0.2").with_package_file("file.h", "0.2")})
    client.run("create . --user=user --channel=channel")

    client.run("lock install lock1.lock")
    assert "pkga/0.1@user/channel from local cache" in client.out
    file_h = client.load("pkga/file.h")
    assert file_h == "0.1"


@pytest.mark.xfail(reason="lockfiles do not work temporarily with new graph, needs to be recovered")
def test_install_recipes():
    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": GenConanfile("pkga", "0.1").with_package_file("file.h", "0.1")})
    client.run("create . --user=user --channel=channel")

    # Use a consumer with a version range
    client.save({"conanfile.py":
                 GenConanfile("pkgb", "0.1").with_require("pkga/[>=0.1]@user/channel")})
    client.run("create . --user=user --channel=channel")
    client.run("lock create --requires=pkgb/0.1@user/channel --lockfile-out=lock1.lock")

    # We can create a pkga/0.2, but it will not be used
    client.save({"conanfile.py": GenConanfile("pkga", "0.2").with_package_file("file.h", "0.2")})
    client.run("create . --user=user --channel=channel")

    client.run("lock install lock1.lock --recipes")
    assert "pkga/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache" in client.out
    assert "pkgb/0.1@user/channel:cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23 - Cache" in client.out

    client.run("upload * -c -r default")
    client.run("remove * -c")
    client.run("lock install lock1.lock --recipes")

    assert "pkga/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Download" in client.out
    assert "pkgb/0.1@user/channel:cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23 - Download" in client.out

