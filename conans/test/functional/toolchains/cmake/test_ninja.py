import textwrap
import unittest
import platform
import os

import pytest

from conan.tools.microsoft.visual import vcvars_command
from conan.tools.cmake.base import CMakeToolchainBase
from conans.test.assets.sources import gen_function_cpp
from conans.test.functional.utils import check_vs_runtime
from conans.test.utils.tools import TestClient


@pytest.mark.tool_cmake
class CMakeNinjaTestCase(unittest.TestCase):
    # This test assumes that 'CMake' and 'Ninja' are available in the system

    main_cpp = gen_function_cpp(name="main")
    cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(App CXX)
        set(CMAKE_VERBOSE_MAKEFILE ON)
        add_executable(App main.cpp)
        install(TARGETS App RUNTIME DESTINATION bin)
        """)
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain

        class Foobar(ConanFile):
            name = "foobar"
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = "*"

            def generate(self):
                tc = CMakeToolchain(self, generator="Ninja")
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.install()
        """)

    conanfile_lib = textwrap.dedent("""
        from conans import ConanFile
        from conans.tools import replace_in_file
        from conan.tools.cmake import CMake, CMakeToolchain

        class foobarConan(ConanFile):
            name = "foobar"
            version = "0.1.0"
            options = {"shared": [True, False]}
            default_options = {"shared": False}
            settings = "os", "compiler", "arch", "build_type"
            exports = '*'

            def generate(self):
                tc = CMakeToolchain(self, generator="Ninja")
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.install()

            def package_info(self):
                self.cpp_info.libs = ["foobar"]
    """)
    cmake_lib = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8.12)
        project(foobar CXX)
        if(CMAKE_VERSION VERSION_LESS "3.15")
            include(${CMAKE_BINARY_DIR}/conan_project_include.cmake)
        endif()
        set(CMAKE_VERBOSE_MAKEFILE ON)
        add_library(foobar hello.cpp hellofoobar.h)
        install(TARGETS foobar RUNTIME DESTINATION bin ARCHIVE DESTINATION lib)
        """)

    @classmethod
    def setUpClass(cls):
        if not which("ninja"):
            raise unittest.SkipTest("Ninja expected in PATH")

    @pytest.mark.skip("Not tested yet")
    def test_locally_build_linux(self):
        """ Ninja build must proceed using default profile and cmake build (Linux)
        """
        client = TestClient(path_with_spaces=False)
        client.save({"linux_host": textwrap.dedent("""
            [settings]
            os=Linux
            arch=x86_64
            compiler=gcc
            compiler.version=10
            compiler.libcxx=libstdc++11
            build_type=Release
            """)})
        self._build_locally(client, "linux_host")
        client.run_command("objdump -f libfoobar.a")
        self.assertIn("architecture: i386:x86-64", client.out)

        self._build_locally(client, "linux_host", "Debug", True)
        client.run_command("objdump -f libfoobard.so")
        self.assertIn("architecture: i386:x86-64", client.out)
        self.assertIn("DYNAMIC", client.out)
        client.run_command("file libfoobard.so")
        # FIXME: Broken assert
        #  self.assertIn("with debug_info", client.out)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
    def test_locally_build_windows(self):
        """ Ninja build must proceed using default profile and cmake build (Windows Release)
        """
        client = TestClient(path_with_spaces=False)
        client.save({"conanfile.py": self.conanfile,
                     "main.cpp": self.main_cpp,
                     "CMakeLists.txt": self.cmake})
        win_host = textwrap.dedent("""
            [settings]
            os=Windows
            arch=x86_64
            compiler=Visual Studio
            compiler.version={}
            compiler.runtime=MD
            build_type={}
            """.format(msvc_version, build_type))
        client.save({"win": win_host})
        client.run("install . -pr=win")
        # Ninja is single-configuration
        vcvars = vcvars_command(msvc_version, architecture="amd64")
        client.run_command('{} && cmake . -G "Ninja" -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake '
                           .format(vcvars))
        client.run_command("{} && cmake --build .".format(vcvars))
        client.run_command("App")
        self.assertIn("main: {}!".format(build_type), client.out)
        self.assertIn("main _M_X64 defined", client.out)

        self.assertIn("main _MSC_VER19", client.out)
        self.assertIn("main _MSVC_LANG2014", client.out)

        check_vs_runtime("App.exe", client, "15", build_type="Release", static=False)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Only windows")
    def test_locally_build_windows_debug(self):
        """ Ninja build must proceed using default profile and cmake build (Windows Debug)
        """
        client = TestClient(path_with_spaces=False)
        client.save({"conanfile.py": self.conanfile,
                     "main.cpp": self.main_cpp,
                     "CMakeLists.txt": self.cmake})
        win_host = textwrap.dedent("""
            [settings]
            os=Windows
            arch=x86
            compiler=Visual Studio
            compiler.version=15
            compiler.runtime=MTd
            build_type=Debug
             """)
        client.save({"win": win_host})
        client.run("install . -pr=win")
        # Ninja is single-configuration
        # It is necessary to set architecture=x86 here, otherwise final architecture is wrong
        vcvars = vcvars_command("15", architecture="x86")
        client.run("install . -pr=win")
        client.run_command('{} && cmake . -G "Ninja" -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake '
                           .format(vcvars))
        client.run_command("{} && cmake --build .".format(vcvars))
        client.run_command("App")
        self.assertIn("main: Debug!", client.out)
        self.assertIn("main _M_IX86 defined", client.out)
        self.assertIn("main _MSC_VER19", client.out)
        self.assertIn("main _MSVC_LANG2014", client.out)

        check_vs_runtime("App.exe", client, "15", build_type="Debug", static=True)
