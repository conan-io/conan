# coding=utf-8

import platform
import textwrap
import unittest

from nose.plugins.attrib import attr
from parameterized.parameterized import parameterized

from conans.client.toolchain.cmake import CMakeToolchain
from conans.client.tools import environment_append
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TurboTestClient


@attr("toolchain")
class FindPackageMultiTestCase(unittest.TestCase):
    """
        Consume a requirements using 'find_package_multi'
    """

    conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake, CMakeToolchain

        class App(ConanFile):
            name = "app"
            version = "version"
            settings = "os", "arch", "compiler", "build_type"
            exports = "*.cpp", "*.txt"
            generators = "cmake_find_package_multi"

            requires = "requirement/version"

            def toolchain(self):
                tc = CMakeToolchain(self)
                return tc

            def build(self):
                # A build helper could be easily added to replace these two lines
                self.run('cmake "%s" -DCMAKE_TOOLCHAIN_FILE=""" + CMakeToolchain.filename + """' % (self.source_folder))

                command_str = "cmake --build ."
                if CMake(self).is_multi_configuration:
                    command_str += " --config {}".format(str(self.settings.build_type))
                self.run(command_str)
                
            def package(self):
                if self.settings.compiler == "Visual Studio":
                    self.copy("{}/app.exe".format(self.settings.build_type), "", keep_path=False)
                else:
                    self.copy("app*", "", "", keep_path=False)
    """)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8)
        project(App CXX)
        
        find_package(requirement REQUIRED)

        add_executable(app src/app.cpp)
        target_link_libraries(app requirement::requirement)
        
        # Pass information to the C++ source so we can print and assert in the tests
        target_compile_definitions(app PRIVATE CMAKE_CXX_COMPILER="${CMAKE_CXX_COMPILER}")
        get_property(_GENERATOR_IS_MULTI_CONFIG GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
        target_compile_definitions(app PRIVATE GENERATOR_IS_MULTI_CONFIG="${_GENERATOR_IS_MULTI_CONFIG}")
        if(NOT ${_GENERATOR_IS_MULTI_CONFIG})
            target_compile_definitions(app PRIVATE CMAKE_BUILD_TYPE="${CMAKE_BUILD_TYPE}")
        endif()
        target_compile_definitions(app PRIVATE "$<$<CONFIG:RELEASE>:NDEBUG>")
        target_compile_definitions(app PRIVATE CMAKE_GENERATOR="${CMAKE_GENERATOR}")
    """)

    app_cpp = textwrap.dedent("""
        #include <iostream>
        #include "hello.h"

        int main() {
            hello();
            #ifdef NDEBUG
                std::cout << "App: Release\\n";
            #else
                std::cout << "App: Debug\\n";
            #endif
            
            std::cout << "CMAKE_CXX_COMPILER: " << CMAKE_CXX_COMPILER << "\\n";
            #ifdef CMAKE_BUILD_TYPE
                std::cout << "CMAKE_BUILD_TYPE: " << CMAKE_BUILD_TYPE << "\\n";
            #endif
            std::cout << "CMAKE_GENERATOR: " << CMAKE_GENERATOR << "\\n";
            std::cout << "GENERATOR_IS_MULTI_CONFIG: " << GENERATOR_IS_MULTI_CONFIG << "\\n";
            return 0;
        }
    """)

    @classmethod
    def setUpClass(cls):
        t = TurboTestClient(path_with_spaces=False)
        # Create the 'requirement' require
        t.run("new requirement/version -s")
        t.run("create . requirement/version@ -s build_type=Release")
        t.run("create . requirement/version@ -s build_type=Debug")
        cls.cache_folder = t.cache_folder

    def setUp(self):
        # Prepare the actual consumer package
        self.app_ref = ConanFileReference.loads("app/version@user/channel")
        self.t = TurboTestClient(path_with_spaces=False, cache_folder=self.cache_folder)
        self.t.save({"conanfile.py": self.conanfile,
                     "CMakeLists.txt": self.cmakelist,
                     "src/app.cpp": self.app_cpp}, clean_first=True)

    @parameterized.expand([("Debug",), ("Release",)])
    def test_cache_create(self, build_type):
        # TODO: Remove? ...It is here just to check that the package builds in the cache
        # Compile the app in the cache
        pref = self.t.create(ref=self.app_ref, conanfile=self.conanfile,
                             args=" -s build_type={}".format(build_type))
        self.assertIn("Using Conan toolchain", self.t.out)

        # Run the app and check it has been properly compiled
        package_layout = self.t.cache.package_layout(pref.ref)
        app_str = "app.exe" if platform.system() == "Windows" else "./app"
        self.t.run_command(app_str, cwd=package_layout.package(pref))
        self.assertIn("Hello World {}!".format(build_type), self.t.out)
        self.assertIn("App: {}".format(build_type), self.t.out)
        # self.assertIn("CMAKE_GENERATOR: ", self.t.out)
        if platform.system() == "Windows":
            self.assertIn("GENERATOR_IS_MULTI_CONFIG: 1", self.t.out)
            self.assertNotIn("CMAKE_BUILD_TYPE", self.t.out)
        else:
            self.assertIn("GENERATOR_IS_MULTI_CONFIG: 0", self.t.out)
            self.assertIn("CMAKE_BUILD_TYPE: {}".format(build_type), self.t.out)

    @parameterized.expand([("Debug",), ("Release",)])
    def test_local_conan(self, build_type):
        # TODO: Remove? ...Here just to check another way of building
        # Conan local workflow
        with self.t.chdir("build"):
            self.t.run("install .. -s build_type={}".format(build_type))
            self.t.run("build ..")
            self.assertIn("Using Conan toolchain", self.t.out)

        # Run the app and check it has been properly compiled
        command_str = "build\\{}\\app.exe".format(build_type) if platform.system() == "Windows" else "./build/app"
        self.t.run_command(command_str)
        self.assertIn("Hello World {}!".format(build_type), self.t.out)
        self.assertIn("App: {}".format(build_type), self.t.out)
        # self.assertIn("CMAKE_GENERATOR: ", self.t.out)
        if platform.system() == "Windows":
            self.assertIn("GENERATOR_IS_MULTI_CONFIG: 1", self.t.out)
            self.assertNotIn("CMAKE_BUILD_TYPE", self.t.out)
        else:
            self.assertIn("GENERATOR_IS_MULTI_CONFIG: 0", self.t.out)
            self.assertIn("CMAKE_BUILD_TYPE: {}".format(build_type), self.t.out)

    @unittest.skipUnless(platform.system() in ["Windows", "Darwin"], "Require multiconfig generator")
    def test_multiconfig_generator(self):
        with self.t.chdir("build"):
            self.t.run("install .. -s build_type=Debug")
            self.t.run("install .. -s build_type=Release")

            # Configure once
            mgenerator = "Xcode" if platform.system() == "Darwin" else "Visual Studio 15 2017 Win64"
            with environment_append({"CMAKE_GENERATOR": mgenerator}):
                cmake_configure = 'cmake .. -DCMAKE_TOOLCHAIN_FILE={}'.format(CMakeToolchain.filename)
                self.t.run_command(cmake_configure)
                self.assertIn("Using Conan toolchain", self.t.out)

            # Test debug
            self.t.run_command("cmake --build . --config Debug")
            command_str = "Debug\\app.exe" if platform.system() == "Windows" else "./Debug/app"
            self.t.run_command(command_str)
            self.assertIn("Hello World Debug!", self.t.out)
            self.assertIn("App: Debug", self.t.out)
            self.assertIn("CMAKE_GENERATOR: {}".format(mgenerator), self.t.out)
            self.assertIn("GENERATOR_IS_MULTI_CONFIG: 1", self.t.out)
            self.assertNotIn("CMAKE_BUILD_TYPE", self.t.out)

            # Test release
            self.t.run_command("cmake --build . --config Release")
            command_str = "Release\\app.exe" if platform.system() == "Windows" else "./Release/app"
            self.t.run_command(command_str)
            self.assertIn("Hello World Release!", self.t.out)
            self.assertIn("App: Release", self.t.out)
            self.assertIn("CMAKE_GENERATOR: {}".format(mgenerator), self.t.out)
            self.assertIn("GENERATOR_IS_MULTI_CONFIG: 1", self.t.out)
            self.assertNotIn("CMAKE_BUILD_TYPE", self.t.out)
