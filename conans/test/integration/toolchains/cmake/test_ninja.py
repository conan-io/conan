import shutil
import textwrap
import unittest

from conans.test.utils.tools import TestClient
from conans.test.utils.test_files import temp_folder
from conans.client.tools import environment_append
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
        add_library(${CMAKE_PROJECT_NAME} foobar.hpp foobar.cpp)
        set_target_properties(${CMAKE_PROJECT_NAME} PROPERTIES PUBLIC_HEADER foobar.hpp)
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

            def package(self):
                cmake = CMake(self)
                cmake.install()
    """)

    @classmethod
    def setUpClass(cls):
        if not shutil.which("ninja"):
            raise unittest.SkipTest("Ninja expected in PATH")

    def setUp(self):
        folder = temp_folder()
        cpp_project = CppProject()
        self.client = TestClient(current_folder=folder)
        cpp_project.create_project(self.client)
        self.client.save({
            "conanfile.py": CMakeNinjaTestCase.conanfile,
        })

    def test_regular_build(self):
        """ Ninja build must proceed using default profile
        """
        with environment_append({"CONAN_CMAKE_GENERATOR": "Ninja"}):
            self.client.run("create . foobar/0.1.0@")
            self.assertIn('CMake command: cmake -G "Ninja" '
                          '-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', self.client.out)

        conanfile = CMakeNinjaTestCase.conanfile.replace("(self)", "(self, generator='Ninja')")
        self.client.save({
            "conanfile.py": conanfile,
        })
        self.client.run("create . foobar/0.1.0@")
        self.assertIn('CMake command: cmake -G "Ninja" '
                      '-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', self.client.out)
