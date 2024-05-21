import textwrap

from conan.test.utils.tools import GenConanfile, TestClient


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
    c.assert_listed_binary({"engine/1.0": ("805fafebc9f7769a90dafb8c008578c6aa7f5d86", "Build")})


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
    new_package_id = "efe870a1b1b4fe60e55aa6e2d17436665404370f"
    assert new_package_id != package_id
    c.assert_listed_binary({"engine/1.0": (new_package_id, "Build")})


class TestDepDefinedMode:
    def test_dep_defined(self):
        c = TestClient()
        dep = textwrap.dedent("""
            from conan import ConanFile
            class Dep(ConanFile):
                name = "dep"
                package_type = "static-library"
                package_id_embed_mode = "major_mode"
                package_id_non_embed_mode = "major_mode"
            """)
        c.save({"dep/conanfile.py": dep,
                "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/[*]")
                                                              .with_shared_option(False)})
        c.run("create dep --version=0.1")
        c.run("create pkg")
        c.assert_listed_binary({"pkg/0.1": ("66a9e6a31e63f77952fd72744d0d5da07970f42e", "Build")})
        c.run("create pkg -o pkg/*:shared=True")
        c.assert_listed_binary({"pkg/0.1": ("5a5828e18eef6a86813b01d4f5a83ea7d87d1139", "Build")})

        # using dep 0.2, still same, because dependency chose "major_mode"
        c.run("create dep --version=0.2")
        c.run("create pkg")
        c.assert_listed_binary({"pkg/0.1": ("66a9e6a31e63f77952fd72744d0d5da07970f42e", "Build")})
        c.run("create pkg -o pkg/*:shared=True")
        c.assert_listed_binary({"pkg/0.1": ("5a5828e18eef6a86813b01d4f5a83ea7d87d1139", "Build")})

    def test_dep_tool_require_defined(self):
        c = TestClient()
        dep = textwrap.dedent("""
            from conan import ConanFile
            class Dep(ConanFile):
                name = "dep"
                package_type = "application"
                build_mode = "minor_mode"
            """)
        c.save({"dep/conanfile.py": dep,
                "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_tool_requires("dep/[*]")})
        c.run("create dep --version=0.1")
        c.run("create pkg")
        c.assert_listed_binary({"pkg/0.1": ("fcf70699eb821f51cd4f3e228341ac4f405ad220", "Build")})

        # using dep 0.2, still same, because dependency chose "minor"
        c.run("create dep --version=0.1.1")
        c.run("create pkg")
        c.assert_listed_binary({"pkg/0.1": ("fcf70699eb821f51cd4f3e228341ac4f405ad220", "Build")})

        # using dep 0.2, still same, because dependency chose "minor"
        c.run("create dep --version=0.2")
        c.run("create pkg")
        c.assert_listed_binary({"pkg/0.1": ("56934f87c11792e356423e081c7cd490f3c1fbe0", "Build")})

    def test_dep_python_require_defined(self):
        c = TestClient()
        dep = textwrap.dedent("""
            from conan import ConanFile
            class Dep(ConanFile):
                name = "dep"
                package_type = "python-require"
                package_id_python_mode = "major_mode"
            """)
        c.save({"dep/conanfile.py": dep,
                "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_python_requires("dep/[*]")})
        c.run("create dep --version=0.1")
        c.run("create pkg")
        c.assert_listed_binary({"pkg/0.1": ("331c17383dcdf37f79bc2b86fa55ac56afdc6fec", "Build")})

        # using dep 0.2, still same, because dependency chose "major"
        c.run("create dep --version=0.1.1")
        c.run("create pkg")
        c.assert_listed_binary({"pkg/0.1": ("331c17383dcdf37f79bc2b86fa55ac56afdc6fec", "Build")})

        # using dep 0.2, still same, because dependency chose "major"
        c.run("create dep --version=0.2")
        c.run("create pkg")
        c.assert_listed_binary({"pkg/0.1": ("331c17383dcdf37f79bc2b86fa55ac56afdc6fec", "Build")})
        c.run("list *:*")
        assert "dep/0.Y.Z" in c.out

        # using dep 0.2, new package_id, because dependency chose "major"
        c.run("create dep --version=1.0")
        c.run("create pkg")
        c.assert_listed_binary({"pkg/0.1": ("9b015e30b768df0217ffa2c270f60227c998e609", "Build")})
        c.run("list *:*")
        assert "dep/1.Y.Z" in c.out
