import shutil
import textwrap
import unittest
import os

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
        folder = temp_folder(False)
        cpp_project = CppProject()
        self.client = TestClient(current_folder=folder)
        cpp_project.create_project(self.client)
        self.client.save({
            "conanfile.py": CMakeNinjaTestCase.conanfile,
        })

    def test_regular_build(self):
        """ Ninja build must proceed using default profile and conan create
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
            # FIXME: conan package tries to install on /usr/local. CMAKE_PREFIX_PATH is empty
            self.client.run("package . --build-folder={} --package-folder={}"
                            .format(build_folder, package_folder), assert_error=True)
            self.assertIn('Permission denied.', self.client.out)
