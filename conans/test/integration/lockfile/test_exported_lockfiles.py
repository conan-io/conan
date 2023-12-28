import os

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


# Bundle-Lockfile
def test_exported_lockfile():
    """ POC: A conan.lock that is exported together with the recipe can be used later while
    consuming that package
    """
    client = TestClient(default_server_user=True)
    client.save({"global.conf": "tools.graph:auto_lock=True"}, path=client.cache_folder)
    client.save({"dep/conanfile.py": GenConanfile("dep"),
                 "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/[*]")})
    client.run("create dep --version=0.1")
    client.run("create pkg")  # captures lockfile in metadata

    client.run("create dep --version=0.2")

    assert "conan.lock" not in os.listdir(client.current_folder)
    client.run("install --requires=pkg/0.1")
    assert "dep/0.2" not in client.out
    assert "dep/0.1" in client.out

    # It should also work when downloading from remote
    client.run("upload * -c -r=default")
    client.run("remove * -c")
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
    client.save({"global.conf": "tools.graph:auto_lock=True"}, path=client.cache_folder)
    client.save({"dep/conanfile.py": GenConanfile("dep"),
                 "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/[*]"),
                 "consumer/conanfile.py": GenConanfile().with_requirement("pkg/0.1")
                                                        .with_requirement("dep/[<0.2]", force=False)})
    client.run("create dep --version=0.1")
    client.run("create dep --version=0.2")
    client.run("create pkg")
    assert "dep/0.2" in client.out
    assert "dep/0.1" not in client.out

    client.run("install consumer --build=missing")
    assert "dep/0.2" not in client.out
    assert "dep/0.1" in client.out
