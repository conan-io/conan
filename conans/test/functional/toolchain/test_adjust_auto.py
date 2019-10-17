# coding=utf-8

import platform
import textwrap
import os
import unittest

from nose.plugins.attrib import attr
from parameterized.parameterized import parameterized
from conans.util.files import load, save
from conans.client.toolchain.cmake import CMakeToolchain
from conans.client.tools import environment_append
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TurboTestClient
from parameterized.parameterized import parameterized_class


def compile_local_workflow(test_case):
    # Conan local workflow
    with test_case.t.chdir("build"):
        test_case.t.run("install .. -s build_type={}".format(test_case.build_type))
        test_case.t.run("build ..")
        test_case.assertIn("Using Conan toolchain", test_case.t.out)

    test_case.t.run_command("./build/app")

    cmake_cache = load(os.path.join(test_case.t.current_folder, "build", "CMakeCache.txt"))
    return test_case.t.out, cmake_cache


def _compile_cache_workflow(test_case, use_toolchain):
    # Compile the app in the cache
    pref = test_case.t.create(ref=test_case.app_ref, conanfile=test_case.conanfile,
                              args=" -s build_type={} -o use_toolchain={}".format(test_case.build_type, use_toolchain))
    test_case.assertIn("Using Conan toolchain", test_case.t.out)

    # Run the app and check it has been properly compiled
    package_layout = test_case.t.cache.package_layout(pref.ref)
    test_case.t.run_command("./app", cwd=package_layout.package(pref))

    cmake_cache = load(os.path.join(package_layout.build(pref), "CMakeCache.txt"))
    return test_case.t.out, cmake_cache


def compile_cache_workflow_with_toolchain(test_case):
    return _compile_cache_workflow(test_case, use_toolchain=True)


def compile_cache_workflow_without_toolchain(test_case):
    return _compile_cache_workflow(test_case, use_toolchain=False)


def compile_cmake_workflow(test_case):
    with test_case.t.chdir("build"):
        test_case.t.run("install .. -s build_type={}".format(test_case.build_type))
        test_case.t.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE={}".format(CMakeToolchain.filename))
        test_case.assertIn("Using Conan toolchain", test_case.t.out)
        test_case.t.run_command("cmake --build . --config {}".format(test_case.build_type))

    test_case.t.run_command("./build/app")

    cmake_cache = load(os.path.join(test_case.t.current_folder, "build", "CMakeCache.txt"))
    return test_case.t.out, cmake_cache


@parameterized_class([#{"function": compile_local_workflow, "build_type": "Debug"},
                      #{"function": compile_local_workflow, "build_type": "Release"},
                      #{"function": compile_cache_workflow, "build_type": "Debug"},
                      #{"function": compile_cache_workflow, "build_type": "Release"},
                      {"function": compile_cmake_workflow, "build_type": "Debug"},
                      {"function": compile_cmake_workflow, "build_type": "Release"},
                      ])
@attr("toolchain")
class AdjustAutoTestCase(unittest.TestCase):
    """
        Consume values from the requirement cpp_info
    """

    conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake, CMakeToolchain

        class App(ConanFile):
            name = "app"
            version = "version"
            settings = "os", "arch", "compiler", "build_type"
            exports = "*.cpp", "*.txt"
            generators = "cmake_find_package", "cmake"
            options = {"use_toolchain": [True, False]}
            default_options = {"use_toolchain": True}

            requires = "requirement/version"

            def toolchain(self):
                tc = CMakeToolchain(self)
                return tc

            def build(self):
                if self.options.use_toolchain:
                    # A build helper could be easily added to replace this two lines
                    self.run('cmake "%s" -DCMAKE_TOOLCHAIN_FILE=""" + CMakeToolchain.filename + """' % (self.source_folder))
                    self.run("cmake --build .")
                else:
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()

            def package(self):
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
        cls.t = TurboTestClient(path_with_spaces=False)
        # Create the 'requirement' require
        cls.t.run("new requirement/version -s")
        cls.t.run("create . requirement/version@ -s build_type=Release")
        cls.t.run("create . requirement/version@ -s build_type=Debug")

    def setUp(self):
        # Prepare the actual consumer package
        self.app_ref = ConanFileReference.loads("app/version@user/channel")
        self.t.save({"conanfile.py": self.conanfile,
                     "CMakeLists.txt": self.cmakelist,
                     "src/app.cpp": self.app_cpp}, clean_first=True)

    def test_build_type(self):
        app_output, cmake_cache = self.function()
        print(cmake_cache)
        self.assertIn("CMAKE_BUILD_TYPE: {}".format(self.build_type), app_output)
        #self.assertIn("CMAKE_BUILD_TYPE: {}".format(self.build_type), cmake_cache)





    """
    @parameterized.expand([("Debug",), ("Release",)])
    def test_cache_create(self, build_type):
        # TODO: Remove. It is here just to check that the package builds in the cache
        # Compile the app in the cache
        pref = self.t.create(ref=self.app_ref, conanfile=self.conanfile,
                             args=" -s build_type={}".format(build_type))
        self.assertIn("Using Conan toolchain", self.t.out)

        # Run the app and check it has been properly compiled
        package_layout = self.t.cache.package_layout(pref.ref)
        self.t.run_command("./app", cwd=package_layout.package(pref))
        self.assertIn("Hello World {}!".format(build_type), self.t.out)
        self.assertIn("App: {}".format(build_type), self.t.out)
        # self.assertIn("CMAKE_GENERATOR: ", self.t.out)
        self.assertIn("GENERATOR_IS_MULTI_CONFIG: 0", self.t.out)
        self.assertIn("CMAKE_BUILD_TYPE: {}".format(build_type), self.t.out)
    """

    """
    @parameterized.expand([("Debug",), ("Release",)])
    def test_local_conan(self, build_type):
        # TODO: Remove. Here just to check another way of building
        # Conan local workflow
        with self.t.chdir("build"):
            self.t.run("install .. -s build_type={}".format(build_type))
            self.t.run("build ..")
            self.assertIn("Using Conan toolchain", self.t.out)

        # Run the app and check it has been properly compiled
        self.t.run_command("./build/app")
        print(self.t.current_folder)
        print(self.t.out)
    """

    """
    self.assertIn("Hello World {}!".format(build_type), self.t.out)
    self.assertIn("App: {}".format(build_type), self.t.out)
    # self.assertIn("CMAKE_GENERATOR: ", self.t.out)
    self.assertIn("GENERATOR_IS_MULTI_CONFIG: 0", self.t.out)
    self.assertIn("CMAKE_BUILD_TYPE: {}".format(build_type), self.t.out)
    """

    """
    @unittest.skipUnless(platform.system() in ["Windows", "Darwin"], "Require multiconfig generator")
    def test_multiconfig_generator(self):
        with self.t.chdir("build"):
            self.t.run("install .. -s build_type=Debug")
            self.t.run("install .. -s build_type=Release")

            # Configure once
            mgenerator = "Xcode" if platform.system() == "Darwin" else "Visual Studio 15 Win64"
            with environment_append({"CMAKE_GENERATOR": mgenerator}):
                cmake_configure = 'cmake .. -DCMAKE_TOOLCHAIN_FILE={}'.format(
                    CMakeToolchain.filename)
                self.t.run_command(cmake_configure)
                self.assertIn("Using Conan toolchain", self.t.out)

            # Test debug
            self.t.run_command("cmake --build . --config Debug")
            self.t.run_command("./Debug/app")
            self.assertIn("Hello World Debug!", self.t.out)
            self.assertIn("App: Debug", self.t.out)
            self.assertIn("CMAKE_GENERATOR: {}".format(mgenerator), self.t.out)
            self.assertIn("GENERATOR_IS_MULTI_CONFIG: 1", self.t.out)
            self.assertNotIn("CMAKE_BUILD_TYPE", self.t.out)

            # Test release
            self.t.run_command("cmake --build . --config Release")
            self.t.run_command("./Release/app")
            self.assertIn("Hello World Release!", self.t.out)
            self.assertIn("App: Release", self.t.out)
            self.assertIn("CMAKE_GENERATOR: {}".format(mgenerator), self.t.out)
            self.assertIn("GENERATOR_IS_MULTI_CONFIG: 1", self.t.out)
            self.assertNotIn("CMAKE_BUILD_TYPE", self.t.out)
    """
