import json

import pytest

from conans.model.recipe_ref import RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_graph_build_order_override_error():
    """
    libc -> libb -> liba -> zlib/1.2
              |--------------/
      |-----override------> zlib/1.3
    """
    c = TestClient()
    c.save({"zlib/conanfile.py": GenConanfile("zlib"),
            "liba/conanfile.py": GenConanfile("liba", "0.1").with_requires("zlib/1.0"),
            "libb/conanfile.py": GenConanfile("libb", "0.1").with_requires("liba/0.1", "zlib/2.0"),
            "libc/conanfile.py": GenConanfile("libc", "0.1").with_requirement("libb/0.1")
                                                            .with_requirement("zlib/3.0",
                                                                              override=True)
            })
    c.run("export zlib --version=2.0")
    c.run("export zlib --version=3.0")
    c.run("export liba")
    c.run("export libb")
    c.run("export libc")
    c.run("graph info --requires=libc/0.1 --lockfile-out=output.lock")

    c.run("graph build-order --requires=libc/0.1 --lockfile=output.lock --order-by=configuration "
          "--build=missing --format=json")

    to_build = json.loads(c.stdout)
    for level in to_build["order"]:
        for package in level:
            binary = package["binary"]
            if binary != "Build":
                continue
            build_args = package["build_args"]
            c.run(f"install {build_args} --lockfile=output.lock")
            ref = RecipeReference.loads(package["ref"])
            assert f"{ref}: Building from source"

    c.run("install --requires=libc/0.1 --lockfile=output.lock")
    # All works, all binaries exist now
    assert "zlib/3.0: Already installed!" in c.out
    assert "liba/0.1: Already installed!" in c.out
    assert "libb/0.1: Already installed!" in c.out
    assert "libc/0.1: Already installed!" in c.out


@pytest.mark.parametrize("replace_pattern", ["*", "3.0"])
def test_graph_build_order_override_replace_requires(replace_pattern):
    """
    libc -> libb -> liba -> zlib/1.2
              |--------------/
      |-----override------> zlib/1.3

    replace_requires zlib -> zlib/system
    """
    c = TestClient()
    c.save({"zlib/conanfile.py": GenConanfile("zlib"),
            "liba/conanfile.py": GenConanfile("liba", "0.1").with_requires("zlib/1.0"),
            "libb/conanfile.py": GenConanfile("libb", "0.1").with_requires("liba/0.1", "zlib/2.0"),
            "libc/conanfile.py": GenConanfile("libc", "0.1").with_requirement("libb/0.1")
                                                            .with_requirement("zlib/3.0",
                                                                              override=True),
            "profile": f"[replace_requires]\nzlib/{replace_pattern}: zlib/system"
            })
    c.run("export zlib --version=2.0")
    c.run("export zlib --version=3.0")
    c.run("export zlib --version=system")
    c.run("export liba")
    c.run("export libb")
    c.run("export libc")
    c.run("lock create --requires=libc/0.1 --lockfile-out=output.lock -pr=profile")

    c.run("graph build-order --requires=libc/0.1 --lockfile=output.lock --order-by=configuration "
          "--build=missing -pr=profile --format=json")

    to_build = json.loads(c.stdout)
    for level in to_build["order"]:
        for package in level:
            binary = package["binary"]
            if binary != "Build":
                continue
            build_args = package["build_args"]
            c.run(f"install {build_args} --lockfile=output.lock -pr=profile")
            ref = RecipeReference.loads(package["ref"])
            assert f"{ref}: Building from source"

    c.run("install --requires=libc/0.1 --lockfile=output.lock -pr=profile")
    # All works, all binaries exist now
    assert "zlib/system: Already installed!" in c.out
    assert "liba/0.1: Already installed!" in c.out
    assert "libb/0.1: Already installed!" in c.out
    assert "libc/0.1: Already installed!" in c.out


def test_single_config_decentralized_overrides():
    r""" same scenario as "test_single_config_centralized()", but distributing the build in
    different build servers, using the "build-order"
    Now with overrides

    pkga -> toola/1.0 -> toolb/1.0 -> toolc/1.0
                \------override-----> toolc/2.0
    pkgb -> toola/2.0 -> toolb/1.0 -> toolc/1.0
                \------override-----> toolc/3.0
    pkgc -> toola/3.0 -> toolb/1.0 -> toolc/1.0
    """
    c = TestClient()
    c.save({"toolc/conanfile.py": GenConanfile("toolc"),
            "toolb/conanfile.py": GenConanfile("toolb").with_requires("toolc/1.0"),
            "toola/conanfile.py": GenConanfile("toola", "1.0").with_requirement("toolb/1.0")
                                                              .with_requirement("toolc/2.0",
                                                                                override=True),
            "toola2/conanfile.py": GenConanfile("toola", "2.0").with_requirement("toolb/1.0")
                                                               .with_requirement("toolc/3.0",
                                                                                 override=True),
            "toola3/conanfile.py": GenConanfile("toola", "3.0").with_requirement("toolb/1.0"),
            "pkga/conanfile.py": GenConanfile("pkga", "1.0").with_tool_requires("toola/1.0"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "1.0").with_requires("pkga/1.0")
                                                            .with_tool_requires("toola/2.0"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "1.0").with_requires("pkgb/1.0")
                                                            .with_tool_requires("toola/3.0"),
            })
    c.run("export toolc --version=1.0")
    c.run("export toolc --version=2.0")
    c.run("export toolc --version=3.0")

    c.run("export toolb --version=1.0")

    c.run("export toola")
    c.run("export toola2")
    c.run("export toola3")

    c.run("export pkga")
    c.run("export pkgb")
    c.run("lock create pkgc")
    lock = json.loads(c.load("pkgc/conan.lock"))
    requires = "\n".join(lock["build_requires"])
    assert "toolc/3.0" in requires
    assert "toolc/2.0" in requires
    assert "toolc/1.0" in requires
    assert len(lock["overrides"]) == 1
    assert set(lock["overrides"]["toolc/1.0"]) == {"toolc/3.0", "toolc/2.0", None}

    c.run("graph build-order pkgc --lockfile=pkgc/conan.lock --format=json --build=missing")
    to_build = json.loads(c.stdout)
    for level in to_build:
        for elem in level:
            for package in elem["packages"][0]:  # assumes no dependencies between packages
                binary = package["binary"]
                if binary != "Build":
                    continue
                build_args = package["build_args"]
                c.run(f"install {build_args} --lockfile=pkgc/conan.lock")

    c.run("install pkgc --lockfile=pkgc/conan.lock")
    # All works, all binaries exist now
    assert "pkga/1.0: Already installed!" in c.out
    assert "pkgb/1.0: Already installed!" in c.out


def test_single_config_decentralized_overrides_nested():
    r""" same scenario as "test_single_config_centralized()", but distributing the build in
    different build servers, using the "build-order"
    Now with overrides

    pkga -> toola/1.0 -> libb/1.0 -> libc/1.0 -> libd/1.0 -> libe/1.0 -> libf/1.0
               \                          \-----------override---------> libf/2.0
                \--------------------override--------------------------> libf/3.0
    """
    c = TestClient()
    c.save({"libf/conanfile.py": GenConanfile("libf"),
            "libe/conanfile.py": GenConanfile("libe", "1.0").with_requires("libf/1.0"),
            "libd/conanfile.py": GenConanfile("libd", "1.0").with_requires("libe/1.0"),
            "libc/conanfile.py": GenConanfile("libc", "1.0").with_requirement("libd/1.0")
                                                            .with_requirement("libf/2.0",
                                                                              override=True),
            "libb/conanfile.py": GenConanfile("libb", "1.0").with_requires("libc/1.0"),
            "toola/conanfile.py": GenConanfile("toola", "1.0").with_requirement("libb/1.0")
                                                              .with_requirement("libf/3.0",
                                                                                override=True),
            "pkga/conanfile.py": GenConanfile("pkga", "1.0").with_tool_requires("toola/1.0"),
            })

    c.run("export libf --version=3.0")
    c.run("export libe")
    c.run("export libd")
    c.run("export libc")
    c.run("export libb")
    c.run("export toola")

    c.run("lock create pkga")
    lock = json.loads(c.load("pkga/conan.lock"))
    assert lock["overrides"] == {"libf/1.0": ["libf/3.0"],
                                 "libf/2.0": ["libf/3.0"]}

    c.run("graph build-order pkga --lockfile=pkga/conan.lock --format=json --build=missing")
    to_build = json.loads(c.stdout)
    for level in to_build:
        for elem in level:
            ref = elem["ref"]
            if "libc" in ref:
                pass
            for package in elem["packages"][0]:  # assumes no dependencies between packages
                binary = package["binary"]
                if binary != "Build":
                    continue
                build_args = package["build_args"]
                c.run(f"install {build_args} --lockfile=pkga/conan.lock")

    c.run("install pkga --lockfile=pkga/conan.lock")
    # All works, all binaries exist now
    assert "Install finished successfully" in c.out


@pytest.mark.parametrize("forced", [False, True])
def test_single_config_decentralized_overrides_multi(forced):
    r""" same scenario as "test_single_config_centralized()", but distributing the build in
    different build servers, using the "build-order"
    Now with overrides

    pkga -> toola/1.0 -> libb/1.0 -> libc/1.0 -> libd/1.0 -> libe/1.0 -> libf/1.0
      |         \                          \-----------override--------> libf/2.0
      |          \--------------------override-------------------------> libf/3.0
    pkgb -> toola/1.1 -> libb/1.0 -> libc/1.0 -> libd/1.0 -> libe/1.0 -> libf/1.0
      |         \                          \-----------override--------> libf/2.0
      |          \--------------------override-------------------------> libf/4.0
    pkgc -> toola/1.2 -> libb/1.0 -> libc/1.0 -> libd/1.0 -> libe/1.0 -> libf/1.0
                                           \-----------override--------> libf/2.0
    """
    override, force = (True, False) if not forced else (False, True)
    c = TestClient()
    c.save({"libf/conanfile.py": GenConanfile("libf"),
            "libe/conanfile.py": GenConanfile("libe", "1.0").with_requires("libf/1.0"),
            "libd/conanfile.py": GenConanfile("libd", "1.0").with_requires("libe/1.0"),
            "libc/conanfile.py": GenConanfile("libc", "1.0").with_requirement("libd/1.0")
                                                            .with_requirement("libf/2.0",
                                                                              override=override,
                                                                              force=force),
            "libb/conanfile.py": GenConanfile("libb", "1.0").with_requires("libc/1.0"),
            "toola/conanfile.py": GenConanfile("toola", "1.0").with_requirement("libb/1.0")
                                                              .with_requirement("libf/3.0",
                                                                                override=override,
                                                                                force=force),
            "toola1/conanfile.py": GenConanfile("toola", "1.1").with_requirement("libb/1.0")
                                                               .with_requirement("libf/4.0",
                                                                                 override=override,
                                                                                 force=force),
            "toola2/conanfile.py": GenConanfile("toola", "1.2").with_requirement("libb/1.0"),
            "pkga/conanfile.py": GenConanfile("pkga", "1.0").with_tool_requires("toola/1.0"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "1.0").with_requires("pkga/1.0")
                                                            .with_tool_requires("toola/1.1"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "1.0").with_requires("pkgb/1.0")
                                                            .with_tool_requires("toola/1.2"),
            })

    c.run("export libf --version=2.0")
    c.run("export libf --version=3.0")
    c.run("export libf --version=4.0")
    c.run("export libe")
    c.run("export libd")
    c.run("export libc")
    c.run("export libb")

    c.run("export toola")
    c.run("export toola1")
    c.run("export toola2")

    c.run("export pkga")
    c.run("export pkgb")
    c.run("lock create pkgc")
    lock = json.loads(c.load("pkgc/conan.lock"))
    assert len(lock["overrides"]) == 2
    assert set(lock["overrides"]["libf/1.0"]) == {"libf/4.0", "libf/2.0", "libf/3.0"}

    if forced:  # When forced, there is one libf/2.0 that is not overriden
        assert set(lock["overrides"]["libf/2.0"]) == {"libf/4.0", "libf/3.0", None}
    else:
        assert set(lock["overrides"]["libf/2.0"]) == {"libf/4.0", "libf/3.0"}

    c.run("graph build-order pkgc --lockfile=pkgc/conan.lock --format=json --build=missing")
    to_build = json.loads(c.stdout)
    for level in to_build:
        for elem in level:
            ref = elem["ref"]
            if "libc" in ref:
                pass
            for package in elem["packages"][0]:  # assumes no dependencies between packages
                binary = package["binary"]
                if binary != "Build":
                    continue
                build_args = package["build_args"]
                c.run(f"install {build_args} --lockfile=pkgc/conan.lock")

    c.run("install pkgc --lockfile=pkgc/conan.lock")
    # All works, all binaries exist now
    assert "pkga/1.0: Already installed!" in c.out
    assert "pkgb/1.0: Already installed!" in c.out


@pytest.mark.parametrize("replace_pattern", ["*", "1.0", "2.0", "3.0", "4.0"])
@pytest.mark.parametrize("forced", [False, True])
def test_single_config_decentralized_overrides_multi_replace_requires(replace_pattern, forced):
    r""" same scenario as "test_single_config_centralized()", but distributing the build in
    different build servers, using the "build-order"
    Now with overrides

    pkga -> toola/1.0 -> libb/1.0 -> libc/1.0 -> libd/1.0 -> libe/1.0 -> libf/1.0
      |         \                          \-----------override--------> libf/2.0
      |          \--------------------override-------------------------> libf/3.0
    pkgb -> toola/1.1 -> libb/1.0 -> libc/1.0 -> libd/1.0 -> libe/1.0 -> libf/1.0
      |         \                          \-----------override--------> libf/2.0
      |          \--------------------override-------------------------> libf/4.0
    pkgc -> toola/1.2 -> libb/1.0 -> libc/1.0 -> libd/1.0 -> libe/1.0 -> libf/1.0
                                           \-----------override--------> libf/2.0
    """
    override, force = (True, False) if not forced else (False, True)
    c = TestClient()
    c.save({"libf/conanfile.py": GenConanfile("libf"),
            "libe/conanfile.py": GenConanfile("libe", "1.0").with_requires("libf/1.0"),
            "libd/conanfile.py": GenConanfile("libd", "1.0").with_requires("libe/1.0"),
            "libc/conanfile.py": GenConanfile("libc", "1.0").with_requirement("libd/1.0")
                                                            .with_requirement("libf/2.0",
                                                                              override=override,
                                                                              force=force),
            "libb/conanfile.py": GenConanfile("libb", "1.0").with_requires("libc/1.0"),
            "toola/conanfile.py": GenConanfile("toola", "1.0").with_requirement("libb/1.0")
                                                              .with_requirement("libf/3.0",
                                                                                override=override,
                                                                                force=force),
            "toola1/conanfile.py": GenConanfile("toola", "1.1").with_requirement("libb/1.0")
                                                               .with_requirement("libf/4.0",
                                                                                 override=override,
                                                                                 force=force),
            "toola2/conanfile.py": GenConanfile("toola", "1.2").with_requirement("libb/1.0"),
            "pkga/conanfile.py": GenConanfile("pkga", "1.0").with_tool_requires("toola/1.0"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "1.0").with_requires("pkga/1.0")
                                                            .with_tool_requires("toola/1.1"),
            "pkgc/conanfile.py": GenConanfile("pkgc", "1.0").with_requires("pkgb/1.0")
                                                            .with_tool_requires("toola/1.2"),
            "profile": f"include(default)\n[replace_requires]\nlibf/{replace_pattern}: libf/system"
            })

    c.run("export libf --version=2.0")
    c.run("export libf --version=3.0")
    c.run("export libf --version=4.0")
    c.run("export libf --version=system")
    c.run("export libe")
    c.run("export libd")
    c.run("export libc")
    c.run("export libb")

    c.run("export toola")
    c.run("export toola1")
    c.run("export toola2")

    c.run("export pkga")
    c.run("export pkgb")
    c.run("lock create pkgc -pr:b=profile")

    # overrides will be different everytime, just checking that things can be built
    c.run("graph build-order pkgc --lockfile=pkgc/conan.lock --format=json -pr:b=profile "
          "--build=missing")

    to_build = json.loads(c.stdout)
    for level in to_build:
        for elem in level:
            ref = elem["ref"]
            if "libc" in ref:
                pass
            for package in elem["packages"][0]:  # assumes no dependencies between packages
                binary = package["binary"]
                if binary != "Build":
                    continue
                build_args = package["build_args"]
                c.run(f"install {build_args} --lockfile=pkgc/conan.lock -pr:b=profile")

    c.run("install pkgc --lockfile=pkgc/conan.lock -pr:b=profile")
    # All works, all binaries exist now
    assert "pkga/1.0: Already installed!" in c.out
    assert "pkgb/1.0: Already installed!" in c.out
    if replace_pattern == "1.0":  # These will overriden by downstream
        assert "libf/system#7fb6d926dabeb955bcea1cafedf953c8 - Cache" not in c.out
    else:
        assert "libf/system#7fb6d926dabeb955bcea1cafedf953c8 - Cache" in c.out
