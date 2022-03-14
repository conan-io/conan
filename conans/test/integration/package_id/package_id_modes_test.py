from conans.test.utils.tools import GenConanfile, TestClient


def test_basic_default_modes_unknown():
    c = TestClient()
    c.save({"matrix/conanfile.py": GenConanfile("matrix"),
            "engine/conanfile.py": GenConanfile("engine", "1.0").with_requires("matrix/[*]")})
    c.run("create matrix --version=1.0")
    c.run("create engine")
    package_id = c.created_package_id("engine/1.0")

    # Using a patch version doesn't kick a engine rebuild
    c.run("create matrix --version=1.0.1")
    c.run("create engine --build=missing")
    c.assert_listed_require({"matrix/1.0.1": "Cache"})
    c.assert_listed_binary({"engine/1.0": (package_id, "Cache")})

    # same with minor version will not need rebuild
    c.run("create matrix --version=1.1.0")
    c.run("create engine --build=missing")
    c.assert_listed_require({"matrix/1.1.0": "Cache"})
    c.assert_listed_binary({"engine/1.0": (package_id, "Cache")})

    # Major will require re-build
    # TODO: Reconsider this default
    c.run("create matrix --version=2.0.0")
    c.run("create engine --build=missing")
    c.assert_listed_require({"matrix/2.0.0": "Cache"})
    c.assert_listed_binary({"engine/1.0": ("11ade076cdae4106ebd55a1c28d29bc7663f919c", "Build")})


def test_basic_default_modes_application():
    """
    if the consumer package is a declared "package_type = "application"" recipe_revision_mode will
    be used
    """
    c = TestClient()
    c.save({"matrix/conanfile.py": GenConanfile("matrix"),
            "engine/conanfile.py": GenConanfile("engine", "1.0").with_requires("matrix/[*]")
                                                                .with_package_type("application")})
    c.run("create matrix --version=1.0")
    c.run("create engine")
    package_id = c.created_package_id("engine/1.0")

    # Using a patch version requires a rebuild
    c.run("create matrix --version=1.0.1")
    c.run("create engine --build=missing")
    c.assert_listed_require({"matrix/1.0.1": "Cache"})
    new_package_id = "d8081b7749215c197cecf386aad03c516bcee5eb"
    assert new_package_id != package_id
    c.assert_listed_binary({"engine/1.0": (new_package_id, "Build")})
