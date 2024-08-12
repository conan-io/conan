import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
def test_transitive_build_scripts():
    c = TestClient()
    scriptsa = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy
        class ScriptsA(ConanFile):
            name = "scriptsa"
            version = "0.1"
            package_type = "build-scripts"
            exports_sources = "*.cmake"
            def package(self):
                copy(self, "*.cmake", src=self.source_folder, dst=self.package_folder)
            def package_info(self):
                self.cpp_info.builddirs = ["."]
            """)
    scriptsa_cmake = textwrap.dedent("""
        function(myfunctionA)
            message(STATUS "MYFUNCTION CMAKE A: Hello world A!!!")
        endfunction()
    """)
    scriptsb = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy
        class ScriptsA(ConanFile):
            name = "scriptsb"
            version = "0.1"
            package_type = "build-scripts"
            exports_sources = "*.cmake"
            def requirements(self):
                self.requires("scriptsa/0.1", run=True, visible=True)
            def package(self):
                copy(self, "*.cmake", src=self.source_folder, dst=self.package_folder)
            def package_info(self):
                self.cpp_info.builddirs = ["."]
            """)
    scriptsb_cmake = textwrap.dedent("""
        find_package(scriptsa)
        function(myfunctionB)
            message(STATUS "MYFUNCTION CMAKE B: Hello world B!!!")
            myfunctionA()
        endfunction()
        """)
    app = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class App(ConanFile):
            package_type = "application"
            generators = "CMakeToolchain"
            settings = "os", "compiler", "arch", "build_type"

            def build_requirements(self):
                self.tool_requires("scriptsb/0.1")
            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)
    app_cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(App LANGUAGES NONE)
        find_package(scriptsb)
        myfunctionB()
    """)
    c.save({"scriptsa/conanfile.py": scriptsa,
            "scriptsa/Findscriptsa.cmake": scriptsa_cmake,
            "scriptsb/conanfile.py": scriptsb,
            "scriptsb/Findscriptsb.cmake": scriptsb_cmake,
            "app/conanfile.py": app,
            "app/CMakeLists.txt": app_cmake})

    c.run("create scriptsa")
    c.run("create scriptsb")
    c.run("build app")

    assert "MYFUNCTION CMAKE B: Hello world B!!!" in c.out
    assert "MYFUNCTION CMAKE A: Hello world A!!!" in c.out


@pytest.mark.tool("cmake")
def test_reuse_macro_from_dep():
    """
    A simple cmake script can be added from a regular requires, without even a ``find_package()``
    https://github.com/conan-io/conan/issues/14013
    """
    c = TestClient()
    pkg = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            package_type = "static-library"
            exports_sources = "*.cmake"
            def package(self):
                copy(self, "*.cmake", src=self.source_folder, dst=self.package_folder)
            def package_info(self):
                self.cpp_info.builddirs = ["."]
            """)
    pkg_macros = textwrap.dedent("""
        function(pkg_macro)
            message(STATUS "PKG MACRO WORKING!!!")
        endfunction()
    """)
    app = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class App(ConanFile):
            package_type = "application"
            generators = "CMakeToolchain"
            settings = "os", "compiler", "arch", "build_type"

            def requirements(self):
                self.requires("pkg/0.1")

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)
    app_cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(App LANGUAGES NONE)

        include(Macros)
        pkg_macro()
    """)
    c.save({"pkg/conanfile.py": pkg,
            "pkg/Macros.cmake": pkg_macros,
            "app/conanfile.py": app,
            "app/CMakeLists.txt": app_cmake})

    c.run("create pkg")
    c.run("build app")

    assert "PKG MACRO WORKING!!!" in c.out

