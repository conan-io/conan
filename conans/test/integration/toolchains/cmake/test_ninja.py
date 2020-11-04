import textwrap
import unittest
import os
import platform

from conans.test.utils.tools import TestClient
from conans.test.utils.test_files import temp_folder
from conans.client.tools import environment_append, which
from conans.client.toolchain.cmake.base import CMakeToolchainBase


class CppProject(object):

    header = textwrap.dedent("""
        #include <string>
        int bar(const std::string& str);
    """)

    source = textwrap.dedent("""
        #include "foobar.hpp"
        #include <iostream>
        int bar(const std::string& str) {
            std::cout << "(BAR): " << str << std::endl;
            return 0;
        }
    """)

    cmakefile = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8.12)
        project(foobar CXX)
        set(CMAKE_VERBOSE_MAKEFILE ON)
        add_library(${CMAKE_PROJECT_NAME} foobar.hpp foobar.cpp)
        set_target_properties(${CMAKE_PROJECT_NAME} PROPERTIES
                              PUBLIC_HEADER foobar.hpp
                              DEBUG_POSTFIX "d")
        install(TARGETS ${CMAKE_PROJECT_NAME}
            RUNTIME DESTINATION bin
            LIBRARY DESTINATION lib
            ARCHIVE DESTINATION lib
            PUBLIC_HEADER DESTINATION include
        )
    """)

    def create_project(self, testclient):
        testclient.save({
            "foobar.hpp": CppProject.header,
            "foobar.cpp": CppProject.source,
            "CMakeLists.txt": CppProject.cmakefile
        })


@unittest.skip("Ninja tests still not working")
class CMakeNinjaTestCase(unittest.TestCase):
    # This test assumes that 'CMake' and 'Ninja' are available in the system

    conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake, CMakeToolchain

        class Foobar(ConanFile):
            name = "foobar"
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = "CMakeLists.txt", "foobar.hpp", "foobar.cpp"
            options = {"shared": [True, False]}
            default_options = {"shared": False}

            def toolchain(self):
                tc = CMakeToolchain(self)
                tc.write_toolchain_files()

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

    def setUp(self):
        folder = temp_folder(False)
        cpp_project = CppProject()
        self.client = TestClient(current_folder=folder)
        cpp_project.create_project(self.client)
        self.client.save({
            "conanfile.py": CMakeNinjaTestCase.conanfile,
        })

    def test_local_cache_build(self):
        """ Ninja build must proceed using default profile and conan create
        """
        with environment_append({"CONAN_CMAKE_GENERATOR": "Ninja"}):
            self.client.run("create . foobar/0.1.0@ --profile:build=default --profile:host=default")
            self.assertIn('CMake command: cmake -G "Ninja" '
                          '-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', self.client.out)

        conanfile = CMakeNinjaTestCase.conanfile.replace("(self)", "(self, generator='Ninja')")
        self.client.save({
            "conanfile.py": conanfile,
        })
        self.client.run("create . foobar/0.1.0@ --profile:build=default --profile:host=default")
        self.assertIn('CMake command: cmake -G "Ninja" '
                      '-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', self.client.out)

    def _build_locally(self, profile="default", build_type="Release", shared=False):
        self.client.run("export . foobar/0.1.0@")
        self.client.run("install . -o foobar:shared={} -s build_type={} -pr:h={} -pr:b=default"
                        .format(shared, build_type, profile))
        self.client.run_command('cmake . -G "Ninja" -DCMAKE_TOOLCHAIN_FILE={}'
                                .format(CMakeToolchainBase.filename))
        self.client.run_command("cmake --build . --config {}".format(build_type))

    @unittest.skipIf(platform.system() != "Linux", "Only linux")
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
                      [env]
                      CONAN_CMAKE_GENERATOR=Ninja""")})
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

    def test_locally_build_Windows(self):
        """ Ninja build must proceed using default profile and cmake build (Windows)
        """
        win_host = textwrap.dedent("""[settings]
                                 os=Windows
                                 arch=x86_64
                                 compiler=Visual Studio
                                 compiler.version=16
                                 compiler.runtime=MD
                                 build_type=Release
                                 [env]
                                 CONAN_CMAKE_GENERATOR=Ninja""")
        self.client.save({"win_host": win_host})
        self._build_locally("win_host")
        self.client.run_command("DUMPBIN /NOLOGO /DIRECTIVES foobar.lib")
        self.assertIn("RuntimeLibrary=MD_Dynamic", self.client.out)
        self.client.run_command("DUMPBIN /NOLOGO /HEADERS foobar.lib")
        self.assertIn("machine (x64)", self.client.out)

        win_host.replace("MD", "MDd")
        self.client.save({"win_host": win_host})
        self._build_locally("win_host", "Debug", False)
        self.client.run_command("DUMPBIN /NOLOGO /DIRECTIVES foobard.lib")
        self.assertIn("RuntimeLibrary=MDd_DynamicDebug", self.client.out)
        self.client.run_command("DUMPBIN /NOLOGO /HEADERS foobard.lib")
        self.assertIn("machine (x64)", self.client.out)

        win_host.replace("MD", "MDd")
        self.client.save({"win_host": win_host})
        self._build_locally("win_host", "Debug", True)
        self.client.run_command("DUMPBIN /NOLOGO /HEADERS foobard.dll")
        self.assertIn("machine (x64)", self.client.out)
        # TODO - How to detect Runtime library from a DLL (command line)?
        # self.client.run_command("DUMPBIN /NOLOGO /DIRECTIVES foobard.dll")
        # self.assertIn("RuntimeLibrary=MDd_DynamicDebug", self.client.out)

    def test_devflow_build(self):
        """ Ninja build must proceed using default profile and conan development flow
        """
        conanfile = CMakeNinjaTestCase.conanfile.replace("(self)", "(self, generator='Ninja')")
        self.client.save({
            "conanfile.py": conanfile,
        })

        build_folder = os.path.join(self.client.current_folder, "build")
        package_folder = os.path.join(self.client.current_folder, "pkg")
        with environment_append({"CONAN_PRINT_RUN_COMMANDS": "1"}):
            self.client.run("export . foobar/0.1.0@")
            self.client.run("install . --install-folder={}".format(build_folder))
            self.client.run("build . --build-folder={}".format(build_folder))
            self.assertIn('CMake command: cmake -G "Ninja" '
                          '-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', self.client.out)
