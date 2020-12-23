import textwrap
import unittest
import platform

import pytest

from conan.tools.microsoft.visual import vcvars_command
from conans.test.assets.sources import gen_function_cpp
from conans.test.functional.utils import check_vs_runtime
from conans.test.utils.tools import TestClient
from conans.client.tools import which

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
            exports_sources = "CMakeLists.txt", "main.cpp"

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

    @classmethod
    def setUpClass(cls):
        if not which("ninja"):
            raise unittest.SkipTest("Ninja expected in PATH")

    @pytest.mark.skip("Not tested yet")
    def test_locally_build_linux(self):
        """ Ninja build must proceed using default profile and cmake build (Linux)
        """
        self.client.save({"linux_host": textwrap.dedent("""
            [settings]
            os=Linux
            arch=x86_64
            compiler=gcc
            compiler.version=10
            compiler.libcxx=libstdc++11
            build_type=Release
            """)})
        self._build_locally("linux_host")
        self.client.run_command("objdump -f libfoobar.a")
        self.assertIn("architecture: i386:x86-64", self.client.out)

        self._build_locally("linux_host", "Debug", True)
        self.client.run_command("objdump -f libfoobard.so")
        self.assertIn("architecture: i386:x86-64", self.client.out)
        self.assertIn("DYNAMIC", self.client.out)
        self.client.run_command("file libfoobard.so")
        # FIXME: Broken assert
        #  self.assertIn("with debug_info", self.client.out)

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
            compiler.version=15
            compiler.runtime=MD
            build_type=Release
             """)
        client.save({"win": win_host})
        client.run("install . -pr=win")
        # Ninja is single-configuration
        vcvars = vcvars_command("15", architecture="amd64")
        client.run_command('{} && cmake . -G "Ninja" -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake '
                           .format(vcvars))
        client.run_command("{} && cmake --build .".format(vcvars))
        client.run_command("App")
        self.assertIn("main: Release!", client.out)
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
