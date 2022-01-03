from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_exported_lockfile():
    """ POC: A conan.lock that is exported together with the recipe can be used later while
    consuming that package
    """
    client = TestClient()
    client.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
                 "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/[*]")
                                                               .with_exports("conan.lock")})
    client.run("create dep")
    with client.chdir("pkg"):
        client.run("lock create conanfile.py --lockfile-out=conan.lock")
        client.run("create .")

    client.save({"dep/conanfile.py": GenConanfile("dep", "0.2")})
    client.run("create dep")

    client.run("install --reference=pkg/0.1")
    assert "dep/0.2" not in client.out
    assert "dep/0.1" in client.out
