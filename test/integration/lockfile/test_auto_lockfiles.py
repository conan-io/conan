import os

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_auto_metadata_lockfile():
    """ POC: A conan.lock that is stored in recipe metadata and used later while resolving graph
    """
    c = TestClient(default_server_user=True)
    c.save({"global.conf": "core.lockfile:auto=True"}, path=c.cache_folder)
    c.save({"dep/conanfile.py": GenConanfile("dep"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/[*]")})
    c.run("create dep --version=0.1")
    c.run("create pkg")  # captures lockfile in metadata
    assert "pkg/0.1: Storing current lockfile in metadata" in c.out

    c.run("create dep --version=0.2")

    assert "conan.lock" not in os.listdir(c.current_folder)
    c.run("install --requires=pkg/0.1")
    assert "pkg/0.1: Using lockfile from metadata" in c.out
    assert "dep/0.2" not in c.out
    assert "dep/0.1" in c.out

    # It should also work when downloading from remote
    c.save({}, clean_first=True)
    c.run("upload * -c -r=default")
    c.run("remove * -c")
    c.run("install --requires=pkg/0.1")
    assert "pkg/0.1: Using lockfile from metadata" in c.out
    assert "dep/0.2" not in c.out
    assert "dep/0.1" in c.out

    c.run("remove * -c")
    c.run("install --requires=pkg/0.1 -cc core.lockfile:auto=False", assert_error=True)
    # Fails with binary missing
    assert "ERROR: Missing prebuilt package for 'pkg/0.1'" in c.out
    assert "pkg/0.1: Using lockfile from metadata" not in c.out
    assert "dep/0.2" in c.out
    assert "dep/0.1" not in c.out


@pytest.mark.parametrize("override", [False, True])
def test_downstream_override(override):
    """
    The downstream lockfile should always have priority.
    Even if the packaged lockfile forces 0.2, if the downstream consumer wants 0.1, it will
    force 0.1. It works for override and regular requires too
    """
    c = TestClient()
    c.save({"global.conf": "core.lockfile:auto=True"}, path=c.cache_folder)
    c.save({"dep/conanfile.py": GenConanfile("dep"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/[*]"),
            "app/conanfile.py": GenConanfile("app", "0.1").with_requirement("pkg/0.1")
                                                          .with_requirement("dep/[<0.2]",
                                                                            override=override)})
    c.run("create dep --version=0.1")
    c.run("create dep --version=0.2")
    c.run("create pkg")
    assert "pkg/0.1: Storing current lockfile in metadata" in c.out
    assert "dep/0.2" in c.out
    assert "dep/0.1" not in c.out

    # verify that the in-recipe lockfile works
    c.run("create dep --version=0.3")
    c.run("install --requires=pkg/0.1")
    assert "dep/0.2" in c.out
    assert "dep/0.3" not in c.out

    # But the consumer will have higher priority
    c.run("install app --build=missing")
    assert "pkg/0.1: Updating existing metadata lockfile with current graph information" in c.out
    # This metadata lockfile will contain now both dep/0.1 and dep/0.2 locked
    # This is not bad per-se, recipe will still default to latest dep/0.2
    assert "dep/0.2" not in c.out
    assert "dep/0.1" in c.out

    c.run("create app")
    c.run("install --requires=app/0.1")
    assert "app/0.1: Using lockfile from metadata" in c.out
    assert "dep/0.2" not in c.out
    assert "dep/0.1" in c.out


def test_diamond():
    c = TestClient()
    c.save({"global.conf": "core.lockfile:auto=True"}, path=c.cache_folder)
    c.save({"dep/conanfile.py": GenConanfile("dep"),
            "pkga/conanfile.py": GenConanfile("pkga", "0.1").with_requires("dep/[*]"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("dep/[*]"),
            "app/conanfile.py": GenConanfile("app", "0.1").with_requires("pkga/0.1", "pkgb/0.1")})
    c.run("create dep --version=0.1")
    c.run("create pkga")
    assert "pkga/0.1: Storing current lockfile in metadata" in c.out
    c.run("create dep --version=0.2")
    c.run("create pkgb")
    assert "pkgb/0.1: Storing current lockfile in metadata" in c.out

    c.run("create dep --version=0.3")  # This should never be used

    # First resolved wins, in this case dep/0.1
    c.run("install app --build=missing")
    assert "pkga/0.1: Using lockfile from metadata" in c.out
    assert "pkgb/0.1: Using lockfile from metadata" in c.out
    assert "dep/0.1" in c.out
    assert "dep/0.2" not in c.out

    c.save({"app/conanfile.py": GenConanfile("app", "0.1").with_requires("pkgb/0.1", "pkga/0.1")})
    # First resolved wins, in this case dep/0.2
    c.run("install app --build=missing")
    assert "pkga/0.1: Using lockfile from metadata" in c.out
    assert "pkgb/0.1: Using lockfile from metadata" in c.out
    assert "dep/0.2" in c.out
    assert "dep/0.1" not in c.out


def test_tree():
    c = TestClient()
    c.save({"global.conf": "core.lockfile:auto=True"}, path=c.cache_folder)
    c.save({"depa/conanfile.py": GenConanfile("depa"),
            "depb/conanfile.py": GenConanfile("depb"),
            "pkga/conanfile.py": GenConanfile("pkga", "0.1").with_requires("depa/[*]"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("depb/[*]"),
            "app/conanfile.py": GenConanfile("app", "0.1").with_requires("pkga/0.1", "pkgb/0.1")})
    c.run("create depa --version=0.1")
    c.run("create pkga")
    assert "pkga/0.1: Storing current lockfile in metadata" in c.out
    c.run("create depb --version=0.1")
    c.run("create pkgb")
    assert "pkgb/0.1: Storing current lockfile in metadata" in c.out

    c.run("create depa --version=0.2")  # This should never be used
    c.run("create depb --version=0.2")  # This should never be used

    c.run("install app --build=missing")
    assert "pkga/0.1: Using lockfile from metadata" in c.out
    assert "pkgb/0.1: Using lockfile from metadata" in c.out
    assert "depa/0.1" in c.out
    assert "depb/0.1" in c.out
    assert "depa/0.2" not in c.out
    assert "depb/0.2" not in c.out

    c.save({"app/conanfile.py": GenConanfile("app", "0.1").with_requires("pkgb/0.1", "pkga/0.1")})
    c.run("install app")
    assert "pkga/0.1: Using lockfile from metadata" in c.out
    assert "pkgb/0.1: Using lockfile from metadata" in c.out
    assert "depa/0.1" in c.out
    assert "depb/0.1" in c.out
    assert "depa/0.2" not in c.out
    assert "depb/0.2" not in c.out
