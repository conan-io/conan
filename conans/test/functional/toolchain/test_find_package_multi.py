# coding=utf-8

import textwrap
import unittest

from conans.client.toolchain.cmake import CMakeToolchain
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TurboTestClient
from conans.client.tools import environment_append


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
                # A build helper could be easily added to replace this
                self.run('cmake "%s" -DCMAKE_TOOLCHAIN_FILE=""" + CMakeToolchain.filename + """' % (self.source_folder))
                self.run("cmake --build .")
                
            def package(self):
                self.copy("app*", "", "", keep_path=False)
    """)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8)
        project(App CXX)
        
        find_package(requirement REQUIRED)

        add_executable(app src/app.cpp)
        target_link_libraries(app requirement::requirement)
        
        # Pass information to the C++ source so we can print and debug it
        target_compile_definitions(app PRIVATE CMAKE_CXX_COMPILER="${CMAKE_CXX_COMPILER}")
        get_property(_GENERATOR_IS_MULTI_CONFIG GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG )
        if(NOT _GENERATOR_IS_MULTI_CONFIG)
            target_compile_definitions(app PRIVATE CMAKE_BUILD_TYPE="${CMAKE_BUILD_TYPE}")
        else()
            target_compile_definitions(app PRIVATE "$<$<CONFIG:RELEASE>:NDEBUG>")
        endif()
        target_compile_definitions(app PRIVATE CMAKE_GENERATOR="${CMAKE_GENERATOR}")
        target_compile_definitions(app PRIVATE CMAKE_GENERATOR_INSTANCE="${CMAKE_GENERATOR_INSTANCE}")
        target_compile_definitions(app PRIVATE CMAKE_GENERATOR_PLATFORM="${CMAKE_GENERATOR_PLATFORM}")
        target_compile_definitions(app PRIVATE CMAKE_GENERATOR_TOOLSET="${CMAKE_GENERATOR_TOOLSET}")
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
            std::cout << "CMAKE_GENERATOR_INSTANCE: " << CMAKE_GENERATOR_INSTANCE << "\\n";
            std::cout << "CMAKE_GENERATOR_PLATFORM: " << CMAKE_GENERATOR_PLATFORM << "\\n";
            std::cout << "CMAKE_GENERATOR_TOOLSET: " << CMAKE_GENERATOR_TOOLSET << "\\n";
            return 0;
        }
    """)

    def setUp(self):
        # TODO: Move to setupClass (at least creating of the requirement)
        self.t = TurboTestClient(path_with_spaces=False)

        # Create the 'Requirement' require
        self.t.run("new requirement/version -s")
        self.t.run("create . requirement/version@ -s build_type=Release")
        self.t.run("create . requirement/version@ -s build_type=Debug")

        # Prepare the actual consumer package
        self.app_ref = ConanFileReference.loads("app/version@user/channel")
        self.t.save({"conanfile.py": self.conanfile,
                     "CMakeLists.txt": self.cmakelist,
                     "src/app.cpp": self.app_cpp}, clean_first=True)

    def _check_cmake_configure_output(self, output):
        # Same output for all the modes
        self.assertIn("Using Conan toolchain through {}.".format(CMakeToolchain.filename),
                      self.t.out)

    def _run_app_cache(self, pref):
        package_layout = self.t.cache.package_layout(pref.ref)
        self.t.run_command("./app", cwd=package_layout.package(pref))

    def test_cache_create(self):
        # TODO: Remove. It is here just to check that the package builds in the cache
        pref = self.t.create(ref=self.app_ref, conanfile=self.conanfile)
        self._check_cmake_configure_output(self.t.out)
        self._run_app_cache(pref)
        print(self.t.out)

    def test_local_conan(self):
        # TODO: Remove. Here just to check another way of building
        # Conan local workflow
        with self.t.chdir("build"):
            self.t.run("install ..")
            self.t.run("build ..")
            self._check_cmake_configure_output(self.t.out)

        self.t.run_command("./build/app")
        print(self.t.out)

    def test_multiconfig_generator(self):
        with self.t.chdir("build"):
            self.t.run("install .. -s build_type=Debug")
            self.t.run("install .. -s build_type=Release")

            with environment_append({"CMAKE_GENERATOR": "Xcode"}):
                cmake_configure = 'cmake .. -DCMAKE_TOOLCHAIN_FILE={}'.format(CMakeToolchain.filename)
                self.t.run_command(cmake_configure)
            self._check_cmake_configure_output(self.t.out)

            # Test debug
            self.t.run_command("cmake --build . --config Debug")
            self.t.run_command("./Debug/app")
            self.assertIn("Hello World Debug!", self.t.out)
            self.assertIn("App: Debug", self.t.out)
            self.assertIn("CMAKE_GENERATOR: Xcode", self.t.out)

            # Test release
            self.t.run_command("cmake --build . --config Release")
            self.t.run_command("./Release/app")
            self.assertIn("Hello World Release!", self.t.out)
            self.assertIn("App: Release", self.t.out)
            self.assertIn("CMAKE_GENERATOR: Xcode", self.t.out)

