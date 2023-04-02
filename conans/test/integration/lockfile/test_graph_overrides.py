from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_graph_overrides():
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkga/0.2",
                                                                              override=True)
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkgb")
    c.run("lock create pkgc")
    lock = c.load("pkgc/conan.lock")
    assert "pkga/0.2" in lock
    assert "pkga/0.1" not in lock
    c.run("graph info pkgc --lockfile=pkgc/conan.lock")
    assert "pkga/0.2" in c.out
    assert "pkga/0.1" not in c.out


def test_graph_overrides_multiple():
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkga/0.2",
                                                                              override=True),
            "pkgd/conanfile.py": GenConanfile("pkgd", "0.1").with_requirement("pkgc/0.1")
                                                            .with_requirement("pkga/0.3",
                                                                              override=True)
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkga --version=0.3")
    c.run("create pkgb")
    c.run("create pkgc --build=missing")
    c.run("lock create pkgd")
    lock = c.load("pkgd/conan.lock")
    assert "pkga/0.3" in lock
    assert "pkga/0.2" not in c.out
    assert "pkga/0.1" not in lock
    c.run("graph info pkgd --lockfile=pkgd/conan.lock")
    assert "pkga/0.3" in c.out
    assert "pkga/0.2" not in c.out
    assert "pkga/0.1" not in c.out


def test_graph_overrides_ranges():
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/[>=0.1 <0.2]"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkga/0.2",
                                                                              override=True)
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


def test_graph_overrides_ranges_inverted():
    """ the override is defining the lower bound of the range
    """
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/[>=0.1]"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkga/0.1",
                                                                              override=True)
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
