import re

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


def test_private_skip():
    # app -> pkg -(private)-> dep
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=dep --version=1.0")
    client.save({"conanfile.py": GenConanfile().with_requirement("dep/1.0", visible=False)})
    client.run("create . --name=pkg --version=1.0")
    client.run("remove dep/1.0:* -c")  # Dep binary is removed not used at all

    client.save({"conanfile.py": GenConanfile().with_requires("pkg/1.0")})
    client.run("create . --name=app --version=1.0 -v")
    client.assert_listed_binary({"dep/1.0": (NO_SETTINGS_PACKAGE_ID, "Skip")})


def test_private_no_skip():
    # app -> pkg -(private)-> dep
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=dep --version=1.0")
    client.save({"conanfile.py": GenConanfile().with_requirement("dep/1.0", visible=False)})
    client.run("create . --name=pkg --version=1.0")

    # But if we want to build pkg, no skip
    client.run("create . --name=app --version=1.0 --build=app/* --build=pkg/*")
    client.assert_listed_binary({"dep/1.0": (NO_SETTINGS_PACKAGE_ID, "Cache")})

    client.run("remove dep/1.0:* -c")  # Dep binary is removed not used at all
    client.run("create . --name=app --version=1.0 --build=app/* --build=pkg/*", assert_error=True)
    client.assert_listed_binary({"dep/1.0": (NO_SETTINGS_PACKAGE_ID, "Missing")})


def test_consumer_no_skip():
    # app -(private)-> pkg -> dep
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=dep --version=1.0")
    client.save({"conanfile.py": GenConanfile().with_requires("dep/1.0")})
    client.run("create . --name=pkg --version=1.0")
    package_id = client.created_package_id("pkg/1.0")
    client.save({"conanfile.py": GenConanfile().with_requirement("pkg/1.0", visible=False)})

    client.run("install . ")

    client.assert_listed_binary({f"dep/1.0": (NO_SETTINGS_PACKAGE_ID, "Cache")})
    client.assert_listed_binary({f"pkg/1.0": (package_id, "Cache")})


def test_shared_link_static_skip():
    # app -> pkg (shared) -> dep (static)
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_shared_option(False)})
    client.run("create . --name=dep --version=1.0")
    package_id = client.created_package_id("dep/1.0")
    client.save({"conanfile.py": GenConanfile().with_requirement("dep/1.0").
                with_shared_option(True)})
    client.run("create . --name=pkg --version=1.0")
    client.run("remove dep/1.0:* -c")  # Dep binary is removed not used at all

    client.save({"conanfile.py": GenConanfile().with_requires("pkg/1.0")})
    client.run("create . --name=app --version=1.0 -v")
    client.assert_listed_binary({"dep/1.0": (package_id, "Skip")})


def test_test_requires():
    # Using a test_requires can be skipped if it is not necessary to build its consumer
    # app -> pkg (static) -(test_requires)-> gtest (static)
    client = TestClient()
    client.save({"conanfile.py": GenConanfile().with_shared_option(False)})
    client.run("create . --name=gtest --version=1.0")
    package_id = client.created_package_id("gtest/1.0")
    client.save({"conanfile.py": GenConanfile().with_test_requires("gtest/1.0").
                with_shared_option(False)})
    client.run("create . --name=pkg --version=1.0")
    client.run("remove gtest/1.0:* -c")  # Dep binary is removed not used at all

    client.save({"conanfile.py": GenConanfile().with_requires("pkg/1.0")})
    # Checking list of skipped binaries
    client.run("create . --name=app --version=1.0")
    assert re.search(r"Skipped binaries(\s*)gtest/1.0", client.out)
    # Showing the complete information about the skipped binary
    client.run("create . --name=app --version=1.0 -v")
    client.assert_listed_binary({"gtest/1.0": (package_id, "Skip")}, test=True)


def test_build_scripts_no_skip():
    c = TestClient()
    c.save({"scripts/conanfile.py": GenConanfile("script", "0.1").with_package_type("build-scripts"),
            "app/conanfile.py": GenConanfile().with_tool_requires("script/0.1")})
    c.run("create scripts")
    c.assert_listed_binary({"script/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Build")},
                           build=True)
    c.run("install app")
    c.assert_listed_binary({"script/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Cache")},
                           build=True)


def test_list_skip_printing():
    """ make sure that when a package is required in the graph, it is not marked as SKIP, just
    because some other part of the graph is skipping it. In this case, a tool_require might be
    necessary for some packages building from soures, but not for others
    """
    c = TestClient()
    c.save({"tool/conanfile.py": GenConanfile("tool", "0.1"),
            "pkga/conanfile.py": GenConanfile("pkga", "0.1").with_tool_requires("tool/0.1"),
            "pkgb/conanfile.py": GenConanfile("pkgb", "0.1").with_requires("pkga/0.1")
                                                            .with_tool_requires("tool/0.1"),
            "app/conanfile.py": GenConanfile().with_requires("pkgb/0.1")})
    c.run("create tool")
    c.run("create pkga")
    c.run("create pkgb")
    c.run("remove pkga:* -c")
    c.run("install app --build=missing")
    c.assert_listed_binary({"tool/0.1": ("da39a3ee5e6b4b0d3255bfef95601890afd80709", "Cache")},
                           build=True)


def test_conf_skip():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    client.run("create . --name=maths --version=1.0")
    client.run("create . --name=ai --version=1.0")

    client.save({"conanfile.py": GenConanfile().with_requirement("maths/1.0", visible=False)})
    client.run("create . --name=liba --version=1.0")
    client.save({"conanfile.py": GenConanfile().with_requirement("ai/1.0", visible=False)})
    client.run("create . --name=libb --version=1.0")

    client.save({"conanfile.py": GenConanfile().with_requires("liba/1.0", "libb/1.0")})
    client.run("create . --name=app --version=0.0 -v")
    client.assert_listed_binary({"maths/1.0": (NO_SETTINGS_PACKAGE_ID, "Skip")})
    client.assert_listed_binary({"ai/1.0": (NO_SETTINGS_PACKAGE_ID, "Skip")})

    client.run("create . --name=app --version=1.0 -v -c *:tools.graph:skip_binaries=False")
    client.assert_listed_binary({"maths/1.0": (NO_SETTINGS_PACKAGE_ID, "Cache")})
    client.assert_listed_binary({"ai/1.0": (NO_SETTINGS_PACKAGE_ID, "Cache")})

    client.run("create . --name=app --version=2.0 -v -c maths/*:tools.graph:skip_binaries=False")
    client.assert_listed_binary({"maths/1.0": (NO_SETTINGS_PACKAGE_ID, "Cache")})
    client.assert_listed_binary({"ai/1.0": (NO_SETTINGS_PACKAGE_ID, "Skip")})

    client.run("create . --name=app --version=3.0 -v -c *:tools.graph:skip_binaries=True")
    client.assert_listed_binary({"maths/1.0": (NO_SETTINGS_PACKAGE_ID, "Skip")})
    client.assert_listed_binary({"ai/1.0": (NO_SETTINGS_PACKAGE_ID, "Skip")})
