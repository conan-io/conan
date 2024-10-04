import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.fixture
def client():
    c = TestClient()
    pkg = textwrap.dedent("""
       from conan import ConanFile
       from conan.tools.cmake import CMakeDeps, CMakeToolchain, CMake
       import os
       class Pkg(ConanFile):
           settings = "build_type", "os", "arch", "compiler"
           requires = "dep/0.1"
           def generate(self):
               tc = CMakeToolchain(self)
               tc.conan_cmakedeps_paths = True
               tc.generate()
               CMakeDeps(self).generate()
           def build(self):
               cmake = CMake(self)
               cmake.configure()
       """)
    cmake = textwrap.dedent("""
       cmake_minimum_required(VERSION 3.15)
       project(pkgb LANGUAGES NONE)
       find_package(dep REQUIRED)
       """)
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "pkg/conanfile.py": pkg,
            "pkg/CMakeLists.txt": cmake})
    return c


@pytest.mark.tool("cmake")
def test_cmake_generated(client):
    c = client
    c.run("create dep")
    c.run("build pkg")
    assert "Conan toolchain: Including CMakeDeps generated conan_find_paths.cmake" in c.out
    assert "Conan: Target declared 'dep::dep'" in c.out


@pytest.mark.tool("cmake")
def test_cmake_in_package(client):
    c = client
    # same, but in-package
    dep = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class Pkg(ConanFile):
            name = "dep"
            version = "0.1"

            def package(self):
                content = 'message(STATUS "Hello from dep dep-Config.cmake!!!!!")'
                save(self, os.path.join(self.package_folder, "dep-config.cmake"), content)
            def package_info(self):
                self.cpp_info.set_property("cmake_find_mode", "none")
        """)

    c.save({"dep/conanfile.py": dep})
    c.run("create dep")
    c.run("build pkg")
    assert "Conan toolchain: Including CMakeDeps generated conan_find_paths.cmake" in c.out
    assert "Hello from dep dep-Config.cmake!!!!!" in c.out
