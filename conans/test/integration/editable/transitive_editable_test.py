import textwrap

from conans.test.utils.tools import TestClient, GenConanfile


def test_transitive_editables_half_diamond():
    # https://github.com/conan-io/conan/issues/4445
    client = TestClient()
    client.save({"libc/conanfile.py": GenConanfile("libc", "0.1"),
                 "libb/conanfile.py": GenConanfile("libb", "0.1").with_require("libc/0.1"),
                 "liba/conanfile.py": GenConanfile("liba", "0.1").with_requires("libb/0.1",
                                                                                "libc/0.1")})
    client.run("editable add libc")
    client.run("create libb")
    client.run("install liba")
    assert "libc/0.1 - Editable" in client.out
    with client.chdir("liba/build"):
        client.run("install ..")
        assert "libc/0.1 - Editable" in client.out


def test_transitive_editable_test_requires():
    """
    This test was crashing because editable packages was "SKIP"ing some dependencies as
    "test_requires", but editables need the dependencies to generate() and to build()

    https://github.com/conan-io/conan/issues/13543
    """
    c = TestClient()
    pkga = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeDeps, cmake_layout

        class Pkg(ConanFile):
            name = "pkga"
            version = "1.0"

            # Binary configuration
            settings = "os", "compiler", "build_type", "arch"

            def build_requirements(self):
                self.test_requires("gtest/1.0")

            def layout(self):
                cmake_layout(self)

            def generate(self):
                cd = CMakeDeps(self)
                cd.generate()
        """)
    pkgb = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import cmake_layout

        class Pkg(ConanFile):
            name = "pkgb"
            version = "1.0"

            # Binary configuration
            settings = "os", "compiler", "build_type", "arch"

            def requirements(self):
                self.requires("pkga/1.0")

            def layout(self):
                cmake_layout(self)
            """)
    c.save({"gtest/conanfile.py": GenConanfile("gtest", "1.0"),
            "pkga/conanfile.py": pkga,
            "pkgb/conanfile.py": pkgb})
    c.run("create gtest")
    c.run("build pkga")
    c.run("editable add pkga")
    # This used to crash, due to paths in test_requires not being processed (package_info() not
    # being called
    c.run("build pkgb")
