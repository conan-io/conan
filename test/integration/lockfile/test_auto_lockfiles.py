import os

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_exported_lockfile():
    """ POC: A conan.lock that is exported together with the recipe can be used later while
    consuming that package
    """
    c = TestClient(default_server_user=True)
    c.save({"global.conf": "core.graph:auto_lock=True"}, path=c.cache_folder)
    c.save({"dep/conanfile.py": GenConanfile("dep"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/[*]")})
    c.run("create dep --version=0.1")
    c.run("create pkg")  # captures lockfile in metadata
    assert "pkg/0.1: Storing current lockfile in metadata" in c.out

    c.run("create dep --version=0.2")

    assert "conan.lock" not in os.listdir(c.current_folder)
    c.run("install --requires=pkg/0.1")
    assert "pkg/0.1: Using lockfile from metadata"
    assert "dep/0.2" not in c.out
    assert "dep/0.1" in c.out

    # It should also work when downloading from remote
    c.save({}, clean_first=True)
    c.run("upload * -c -r=default")
    c.run("remove * -c")
    c.run("install --requires=pkg/0.1")
    assert "pkg/0.1: Using lockfile from metadata"
    assert "dep/0.2" not in c.out
    assert "dep/0.1" in c.out


@pytest.mark.parametrize("override", [False, True])
def test_downstream_override(override):
    """
    The downstream lockfile should always have priority.
    Even if the packaged lockfile forces 0.2, if the downstream consumer wants 0.1, it will
    force 0.1. It works for override and regular requires too
    """
    c = TestClient()
    c.save({"global.conf": "core.graph:auto_lock=True"}, path=c.cache_folder)
    c.save({"dep/conanfile.py": GenConanfile("dep"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/[*]"),
            "app/conanfile.py": GenConanfile("app", "0.1").with_requirement("pkg/0.1")
                                                          .with_requirement("dep/[<0.2]",
                                                                            override=override)})
    c.run("create dep --version=0.1")
    c.run("create dep --version=0.2")
    c.run("create pkg")
    assert "dep/0.2" in c.out
    assert "dep/0.1" not in c.out

    # verify that the in-recipe lockfile works
    c.run("create dep --version=0.3")
    c.run("install --requires=pkg/0.1")
    assert "dep/0.2" in c.out
    assert "dep/0.3" not in c.out

    # But the consumer will have higher priority
    c.run("install app --build=missing")
    assert "dep/0.2" not in c.out
    assert "dep/0.1" in c.out

    c.run("create app")
    # it will also contain a lockfile inside app
    c.run("install --requires=app/0.1")
    assert "dep/0.2" not in c.out
    assert "dep/0.1" in c.out


def test_diamond():
    c = TestClient()
    c.save({"global.conf": "core.graph:auto_lock=True"}, path=c.cache_folder)
    c.save({"dep/conanfile.py": GenConanfile("dep"),
            "pkga/conanfile.py": GenConanfile("pkga", "0.1").with_requires("dep/[*]"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("dep/[*]"),
            "app/conanfile.py": GenConanfile("app", "0.1").with_requires("pkga/0.1", "pkgb/0.1")})
    c.run("create dep --version=0.1")
    c.run("create pkga")
    c.run("create dep --version=0.2")
    c.run("create pkgb")

    # First resolved wins, in this case dep/0.1
    c.run("install app --build=missing")
    assert "dep/0.1" in c.out
    assert "dep/0.2" not in c.out

    c.save({"app/conanfile.py": GenConanfile("app", "0.1").with_requires("pkgb/0.1", "pkga/0.1")})
    # First resolved wins, in this case dep/0.1
    c.run("install app --build=missing")
    assert "dep/0.2" in c.out
    assert "dep/0.1" not in c.out
