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
    client.run("create . --name=app --version=1.0")
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
    client.run("create . --name=app --version=1.0")
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
    client.run("create . --name=app --version=1.0")
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
