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
        client.run("lock create .")
        client.run("create .")

    client.save({"dep/conanfile.py": GenConanfile("dep", "0.2")})
    client.run("create dep")

    client.run("install --requires=pkg/0.1")
    assert "dep/0.2" not in client.out
    assert "dep/0.1" in client.out


def test_downstream_priority():
    """ The downstream lockfile should always have priority. So far it works, because
    a) when the consumer locks, it is already using the same set of locked dependencies
    b) if the consumer forces other versions different to dependency locked ones, they will have
       priority anyway, irrespective of the merge. The merge at the moment is still prioritizing
       the latest, which might not be the downstream locked one
    The possible way to achieve a failure in this approach at the moment is if we implement a
    "ignore exported lockfiles" config, so downstream consumer can lock to a different version
    that doesn't match the dependency one
    """
    client = TestClient()
    client.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
                 "dep2/conanfile.py": GenConanfile("dep", "0.2"),
                 "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/[*]")
                                                               .with_exports("conan.lock"),
                 "consumer/conanfile.py": GenConanfile().with_requirement("pkg/0.1")
                                                        .with_requirement("dep/[<0.2]", force=True)})
    client.run("create dep")
    client.run("create dep2")
    with client.chdir("pkg"):
        client.run("lock create .")
        client.run("create .")
        assert "dep/0.2" in client.out
        assert "dep/0.1" not in client.out

    with client.chdir("consumer"):
        client.run("lock create .")
        client.run("install . --build=missing --lockfile=conan.lock")
        assert "dep/0.2" not in client.out
        assert "dep/0.1" in client.out
