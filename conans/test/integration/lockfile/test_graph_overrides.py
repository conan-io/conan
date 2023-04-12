import json

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.mark.parametrize("override, force", [(True, False), (False, True)])
def test_graph_overrides(override, force):
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkga/0.2",
                                                                              override=override,
                                                                              force=force)
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkgb")
    c.run("lock create pkgc")
    lock = json.loads(c.load("pkgc/conan.lock"))
    requires = "\n".join(lock["requires"])
    assert "pkga/0.2" in requires
    assert "pkga/0.1" not in requires
    c.run("graph info pkgc --lockfile=pkgc/conan.lock --format=json")
    assert "pkga/0.2" in c.stdout
    assert "pkga/0.1" not in c.stdout
    # apply the lockfile to pkgb, should it lock to pkga/0.2
    c.run("graph info pkgb --lockfile=pkgc/conan.lock --format=json")
    assert "pkga/0.2" in c.stdout
    assert "pkga/0.1" not in c.stdout


@pytest.mark.parametrize("override1, force1", [(True, False), (False, True)])
@pytest.mark.parametrize("override2, force2", [(True, False), (False, True)])
def test_graph_overrides_multiple(override1, force1, override2, force2):
    r"""
    pkgd/0.1 -> pkgc/0.1 -> pkgb/0.1 -> pkga/0.1
      \           \--override---------> pkga/0.2
       \---override-------------------> pkga/0.3
    """
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkga/0.2",
                                                                              override=override1,
                                                                              force=force1),
            "pkgd/conanfile.py": GenConanfile("pkgd", "0.1").with_requirement("pkgc/0.1")
                                                            .with_requirement("pkga/0.3",
                                                                              override=override2,
                                                                              force=force2)
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkga --version=0.3")
    c.run("create pkgb")
    c.run("create pkgc --build=missing")
    c.run("lock create pkgd")
    lock = json.loads(c.load("pkgd/conan.lock"))
    requires = "\n".join(lock["requires"])
    assert "pkga/0.3" in requires
    assert "pkga/0.2" not in requires
    assert "pkga/0.1" not in requires
    c.run("graph info pkgd --lockfile=pkgd/conan.lock")
    print(c.out)
    assert "pkga/0.3" in c.out
    assert "pkga/0.2#" not in c.out
    assert "pkga/0.1#" not in c.out  # appears in override information


@pytest.mark.parametrize("override, force", [(True, False), (False, True)])
def test_graph_overrides_ranges(override, force):
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/[>=0.1 <0.2]"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkga/0.2",
                                                                              override=override,
                                                                              force=force)
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkgb")
    assert "pkga/0.2" not in c.out
    assert "pkga/0.1" in c.out
    c.run("lock create pkgc")
    lock = c.load("pkgc/conan.lock")
    assert "pkga/0.2" in lock
    assert "pkga/0.1" not in lock
    c.run("graph info pkgc --lockfile=pkgc/conan.lock")
    assert "pkga/0.2" in c.out
    assert "pkga/0.1" not in c.out


@pytest.mark.parametrize("override, force", [(True, False), (False, True)])
def test_graph_overrides_ranges_inverted(override, force):
    """ the override is defining the lower bound of the range
    """
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/[>=0.1]"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkga/0.1",
                                                                              override=override,
                                                                              force=force)
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkgb")
    assert "pkga/0.2" in c.out
    assert "pkga/0.1" not in c.out
    c.run("lock create pkgc")
    lock = c.load("pkgc/conan.lock")
    assert "pkga/0.1" in lock
    assert "pkga/0.2" not in lock
    c.run("graph info pkgc --lockfile=pkgc/conan.lock")
    assert "pkga/0.1" in c.out
    assert "pkga/0.2" not in c.out


def test_graph_different_overrides():
    r"""
    pkga -> toola/0.1 -> toolb/0.1 -> toolc/0.1
                \------override-----> toolc/0.2
    pkgb -> toola/0.2 -> toolb/0.2 -> toolc/0.1
                \------override-----> toolc/0.3
    pkgc -> toola/0.3 -> toolb/0.3 -> toolc/0.1
    """
    c = TestClient()
    c.save({"toolc/conanfile.py": GenConanfile("toolc"),
            "toolb/conanfile.py": GenConanfile("toolb").with_requires("toolc/0.1"),
            "toola/conanfile.py": GenConanfile("toola", "0.1").with_requirement("toolb/0.1")
                                                              .with_requirement("toolc/0.2",
                                                                                override=True),
            "toola2/conanfile.py": GenConanfile("toola", "0.2").with_requirement("toolb/0.2")
                                                               .with_requirement("toolc/0.3",
                                                                                 override=True),
            "toola3/conanfile.py": GenConanfile("toola", "0.3").with_requirement("toolb/0.3"),
            "pkga/conanfile.py": GenConanfile("pkga", "0.1").with_tool_requires("toola/0.1"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1")
                                                            .with_tool_requires("toola/0.2"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requires("pkgb/0.1")
                                                            .with_tool_requires("toola/0.3"),
            })
    c.run("create toolc --version=0.1")
    c.run("create toolc --version=0.2")
    c.run("create toolc --version=0.3")

    c.run("create toolb --version=0.1")
    c.run("create toolb --version=0.2")
    c.run("create toolb --version=0.3")

    c.run("create toola --build=missing")
    c.run("create toola2 --build=missing")
    c.run("create toola3 --build=missing")

    c.run("create pkga")
    c.run("create pkgb")
    c.run("lock create pkgc")
    lock = json.loads(c.load("pkgc/conan.lock"))
    requires = "\n".join(lock["build_requires"])
    assert "toolc/0.3" in requires
    assert "toolc/0.2" in requires
    assert "toolc/0.1" in requires

    c.run("graph info toolb --build-require --version=0.1 --lockfile=pkgc/conan.lock --format=json")
    c.assert_listed_require({"toolc/0.2": "Cache"}, build=True)
    c.run("graph info toolb --build-require --version=0.2 --lockfile=pkgc/conan.lock --format=json")
    c.assert_listed_require({"toolc/0.3": "Cache"}, build=True)
    c.run("graph info toolb --build-require --version=0.3 --lockfile=pkgc/conan.lock --format=json")
    c.assert_listed_require({"toolc/0.1": "Cache"}, build=True)


def test_graph_same_base_overrides():
    r"""
    pkga -> toola/0.1 -> toolb/0.1 -> toolc/0.1
                \------override-----> toolc/0.2
    pkgb -> toola/0.2 -> toolb/0.1 -> toolc/0.1
                \------override-----> toolc/0.3
    pkgc -> toola/0.3 -> toolb/0.1 -> toolc/0.1
    """
    c = TestClient()
    c.save({"toolc/conanfile.py": GenConanfile("toolc"),
            "toolb/conanfile.py": GenConanfile("toolb").with_requires("toolc/0.1"),
            "toola/conanfile.py": GenConanfile("toola", "0.1").with_requirement("toolb/0.1")
                                                              .with_requirement("toolc/0.2",
                                                                                override=True),
            "toola2/conanfile.py": GenConanfile("toola", "0.2").with_requirement("toolb/0.1")
                                                               .with_requirement("toolc/0.3",
                                                                                 override=True),
            "toola3/conanfile.py": GenConanfile("toola", "0.3").with_requirement("toolb/0.1"),
            "pkga/conanfile.py": GenConanfile("pkga", "0.1").with_tool_requires("toola/0.1"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1")
                                                            .with_tool_requires("toola/0.2"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requires("pkgb/0.1")
                                                            .with_tool_requires("toola/0.3"),
            })
    c.run("create toolc --version=0.1")
    c.run("create toolc --version=0.2")
    c.run("create toolc --version=0.3")

    c.run("create toolb --version=0.1")

    c.run("create toola --build=missing")
    c.run("create toola2 --build=missing")
    c.run("create toola3 --build=missing")

    c.run("create pkga")
    c.run("create pkgb")
    c.run("lock create pkgc")
    lock = json.loads(c.load("pkgc/conan.lock"))
    print(c.load("pkgc/conan.lock"))
    requires = "\n".join(lock["build_requires"])
    assert "toolc/0.3" in requires
    assert "toolc/0.2" in requires
    assert "toolc/0.1" in requires

    c.run("graph info toolb --build-require --version=0.1 --lockfile=pkgc/conan.lock --format=json")
    print(c.out)
    #assert "Override for toolb/0.1->toolc/0.1 cannot be resolved" in c.out
    c.assert_listed_require({"toolc/0.1": "Cache"}, build=True)

    c.run("graph info pkgc --filter=requires")
    print(c.out)
    c.run("graph build-order pkgc --lockfile=pkgc/conan.lock --format=json --build=*")
    print(c.stdout)
    build_order = json.loads(c.stdout)

