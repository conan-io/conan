from conans.test.utils.tools import TestClient, GenConanfile


def test_install():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("pkga", "0.1").with_package_file("file.h", "0.1")})
    client.run("create . user/channel")

    # Use a consumer with a version range
    client.save({"conanfile.py":
                 GenConanfile("pkgb", "0.1").with_require("pkga/[>=0.1]@user/channel")})
    client.run("create . user/channel")
    client.run("lock create --reference=pkgb/0.1@user/channel --lockfile-out=lock1.lock")

    # We can create a pkga/0.2, but it will not be used
    client.save({"conanfile.py": GenConanfile("pkga", "0.2").with_package_file("file.h", "0.2")})
    client.run("create . user/channel")

    client.run("lock install lock1.lock -g deploy")
    assert "pkga/0.1@user/channel from local cache" in client.out
    file_h = client.load("pkga/file.h")
    assert file_h == "0.1"


def test_install_recipes():
    client = TestClient(default_server_user=True)
    client.save({"conanfile.py": GenConanfile("pkga", "0.1").with_package_file("file.h", "0.1")})
    client.run("create . user/channel")

    # Use a consumer with a version range
    client.save({"conanfile.py":
                 GenConanfile("pkgb", "0.1").with_require("pkga/[>=0.1]@user/channel")})
    client.run("create . user/channel")
    client.run("lock create --reference=pkgb/0.1@user/channel --lockfile-out=lock1.lock")

    # We can create a pkga/0.2, but it will not be used
    client.save({"conanfile.py": GenConanfile("pkga", "0.2").with_package_file("file.h", "0.2")})
    client.run("create . user/channel")

    client.run("lock install lock1.lock --recipes")
    assert "pkga/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache" in client.out
    assert "pkgb/0.1@user/channel:cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23 - Cache" in client.out

    client.run("upload * --all -c")
    client.run("remove * -f")
    client.run("lock install lock1.lock --recipes")

    assert "pkga/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Download" in client.out
    assert "pkgb/0.1@user/channel:cfd10f60aeaa00f5ca1f90b5fe97c3fe19e7ec23 - Download" in client.out

