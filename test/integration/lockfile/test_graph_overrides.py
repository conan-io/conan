import json

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("override, force", [(True, False), (False, True)])
def test_overrides_half_diamond(override, force):
    r"""
    pkgc -----> pkgb/0.1 --> pkga/0.1
       \--(override/force)-->pkga/0.2
    """
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
    dependencies = json.loads(c.stdout)["graph"]["nodes"]["0"]["dependencies"]
    assert "pkga/0.2" in str(dependencies)
    assert "pkga/0.1" not in str(dependencies)
    # apply the lockfile to pkgb, should it lock to pkga/0.2
    c.run("graph info pkgb --lockfile=pkgc/conan.lock --format=json")
    dependencies = json.loads(c.stdout)["graph"]["nodes"]["0"]["dependencies"]
    assert "pkga/0.2" in str(dependencies)
    assert "pkga/0.1" not in str(dependencies)


@pytest.mark.parametrize("override, force", [(True, False), (False, True)])
def test_overrides_half_diamond_ranges(override, force):
    r"""
       pkgc -----> pkgb/0.1 --> pkga/[>0.1 <0.2]
          \--(override/force)-->pkga/0.2
    """
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
def test_overrides_half_diamond_ranges_inverted(override, force):
    r""" the override is defining the lower bound of the range

       pkgc -----> pkgb/0.1 --> pkga/[>=0.1]
          \--(override/force)-->pkga/0.1
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


@pytest.mark.parametrize("override, force", [(True, False), (False, True)])
def test_overrides_diamond(override, force):
    r"""
    pkgd -----> pkgb/0.1 --> pkga/0.1
       \------> pkgc/0.1 --> pkga/0.2
       \--(override/force)-->pkga/0.3
    """
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requires("pkga/0.2"),
            "pkgd/conanfile.py": GenConanfile("pkgd", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkgc/0.1")
                                                            .with_requirement("pkga/0.3",
                                                                              override=override,
                                                                              force=force)
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkga --version=0.3")
    c.run("create pkgb")
    c.run("create pkgc")
    c.run("lock create pkgd")
    lock = json.loads(c.load("pkgd/conan.lock"))
    requires = "\n".join(lock["requires"])
    assert "pkga/0.3" in requires
    assert "pkga/0.2" not in requires
    assert "pkga/0.1" not in requires
    c.run("graph info pkgd --lockfile=pkgd/conan.lock --format=json")
    json_graph = json.loads(c.stdout)
    deps = json_graph["graph"]["nodes"]["0"]["dependencies"]
    assert "pkga/0.3" in str(deps)
    assert "pkga/0.2" not in str(deps)
    assert "pkga/0.1" not in str(deps)
    # Redundant assert, but checking "overrides" summary
    overrides = json_graph['graph']["overrides"]
    assert len(overrides) == 2
    assert overrides['pkga/0.1'] == ['pkga/0.3']
    assert overrides['pkga/0.2'] == ['pkga/0.3']

    # apply the lockfile to pkgb, should it lock to pkga/0.3
    c.run("graph info pkgb --lockfile=pkgd/conan.lock --format=json")
    json_graph = json.loads(c.stdout)
    deps = json_graph["graph"]["nodes"]["0"]["dependencies"]
    assert "pkga/0.3" in str(deps)
    assert "pkga/0.2" not in str(deps)
    assert "pkga/0.1" not in str(deps)
    # Redundant assert, but checking "overrides" summary
    overrides = json_graph['graph']["overrides"]
    assert len(overrides) == 1
    assert overrides["pkga/0.1"] == ["pkga/0.3"]


@pytest.mark.parametrize("override, force", [(True, False), (False, True)])
def test_overrides_diamond_ranges(override, force):
    r"""
    pkgd -----> pkgb/0.1 --> pkga/[>=0.1 <0.2]
       \------> pkgc/0.1 --> pkga/[>=0.2 <0.3]
       \--(override/force)-->pkga/0.3
    """
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/[>=0.1 <0.2]"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requires("pkga/[>=0.2 <0.3]"),
            "pkgd/conanfile.py": GenConanfile("pkgd", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkgc/0.1")
                                                            .with_requirement("pkga/0.3",
                                                                              override=override,
                                                                              force=force)
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkga --version=0.3")
    c.run("create pkgb")
    c.run("create pkgc")
    c.run("lock create pkgd")
    lock = json.loads(c.load("pkgd/conan.lock"))
    requires = "\n".join(lock["requires"])
    assert "pkga/0.3" in requires
    assert "pkga/0.2" not in requires
    assert "pkga/0.1" not in requires
    c.run("graph info pkgd --lockfile=pkgd/conan.lock --format=json")
    dependencies = json.loads(c.stdout)["graph"]["nodes"]["0"]["dependencies"]
    assert "pkga/0.3" in str(dependencies)
    assert "pkga/0.2" not in str(dependencies)
    assert "pkga/0.1" not in str(dependencies)
    # apply the lockfile to pkgb, should it lock to pkga/0.3
    c.run("graph info pkgb --lockfile=pkgd/conan.lock --format=json")
    dependencies = json.loads(c.stdout)["graph"]["nodes"]["0"]["dependencies"]
    assert "pkga/0.3" in str(dependencies)
    assert "pkga/0.2" not in str(dependencies)
    assert "pkga/0.1" not in str(dependencies)


@pytest.mark.parametrize("override1, force1", [(True, False), (False, True)])
@pytest.mark.parametrize("override2, force2", [(True, False), (False, True)])
def test_overrides_multiple(override1, force1, override2, force2):
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
    assert "pkga/0.3" in c.out
    assert "pkga/0.2#" not in c.out
    assert "pkga/0.1#" not in c.out  # appears in override information


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
    # defaults to the non overriden
    c.assert_listed_require({"toolc/0.1": "Cache"}, build=True)
    # TODO: Solve it with build-order or manual overrides for the other packages


@pytest.mark.parametrize("override, force", [(True, False), (False, True)])
def test_introduced_conflict(override, force):
    """
    Using --lockfile-partial we can evaluate and introduce a new conflict
    pkgd -----> pkgb/[*] --> pkga/[>=0.1 <0.2]
    """
    c = TestClient()
    c.save({"pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb").with_requires("pkga/[>=0.1 <0.2]"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requires("pkga/[>=0.2 <0.3]"),
            "pkgd/conanfile.py": GenConanfile("pkgd", "0.1").with_requirement("pkgb/[*]")
            })
    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkga --version=0.3")
    c.run("create pkgb --version=0.1")
    c.run("create pkgc")
    c.run("lock create pkgd")
    lock = json.loads(c.load("pkgd/conan.lock"))
    requires = "\n".join(lock["requires"])
    assert "pkga/0.1" in requires
    assert "pkga/0.2" not in requires
    assert "pkga/0.3" not in requires
    # This will not be used thanks to the lockfile
    c.run("create pkgb --version=0.2")

    """
    This change in pkgd introduce a conflict
        Using --lockfile-partial we can evaluate and introduce a new conflict
        pkgd -----> pkgb/[*] --> pkga/[>=0.1 <0.2]
          |-------> pkgc/0.1 --> pkga/[>=0.2 <0.3]
    """
    c.save({"pkgd/conanfile.py": GenConanfile("pkgd", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkgc/0.1")
            })

    c.run("graph info pkgd --lockfile=pkgd/conan.lock --lockfile-partial", assert_error=True)
    assert "Version conflict: Conflict between pkga/[>=0.2 <0.3] and pkga/0.1 in the graph" in c.out
    # Resolve the conflict with an override or force
    c.save({"pkgd/conanfile.py": GenConanfile("pkgd", "0.1").with_requirement("pkgb/0.1")
                                                            .with_requirement("pkgc/0.1")
                                                            .with_requirement("pkga/0.3",
                                                                              override=override,
                                                                              force=force)
            })
    c.run("graph info pkgd --lockfile=pkgd/conan.lock --lockfile-partial "
          "--lockfile-out=pkgd/conan2.lock --lockfile-clean")
    assert "pkgb/0.2" not in c.out
    assert "pkgb/0.1" in c.out
    lock = json.loads(c.load("pkgd/conan2.lock"))
    requires = "\n".join(lock["requires"])
    assert "pkga/0.3" in requires
    assert "pkga/0.1" not in requires
    assert "pkga/0.2" not in requires
    assert "pkgb/0.2" not in requires


def test_command_line_lockfile_overrides():
    """
    --lockfile-overrides cannot be abused to inject new overrides, only existing ones
    """
    c = TestClient()
    c.save({
            "pkga/conanfile.py": GenConanfile("pkga"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requires("pkgb/0.1"),
            })

    c.run("create pkga --version=0.1")
    c.run("create pkga --version=0.2")
    c.run("create pkgb")
    c.run('install pkgc --lockfile-overrides="{\'pkga/0.1\': [\'pkga/0.2\']}"', assert_error=True)
    assert "Cannot define overrides without a lockfile" in c.out
    c.run('lock create pkgc')
    c.run('install pkgc --lockfile-overrides="{\'pkga/0.1\': [\'pkga/0.2\']}"', assert_error=True)
    assert "Requirement 'pkga/0.2' not in lockfile" in c.out


def test_consecutive_installs():
    c = TestClient()
    c.save({
        "pkga/conanfile.py": GenConanfile("pkga"),
        "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1"),
        "pkgc/conanfile.py": GenConanfile("pkgc", "0.1").with_requires("pkgb/0.1")
                                                        .with_requirement("pkga/0.2", override=True),
    })
    c.run("export pkga --version=0.1")
    c.run("export pkga --version=0.2")
    c.run("export pkgb")
    c.run("install pkgc --build=missing --lockfile-out=conan.lock")
    c.assert_overrides({"pkga/0.1": ["pkga/0.2"]})
    # This used to crash when overrides were not managed
    c.run("install pkgc --build=missing --lockfile=conan.lock --lockfile-out=conan.lock")
    c.assert_overrides({"pkga/0.1": ["pkga/0.2"]})
