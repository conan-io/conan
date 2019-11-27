# coding=utf-8

import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr
from parameterized.parameterized import parameterized

from conans.client.toolchain.cmake import CMakeToolchain
from conans.client.tools import environment_append
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TurboTestClient
from conans.util.files import load, rmdir


@attr("toolchain")
class FindPackageMultiTestCase(unittest.TestCase):
    """
        Consume a requirements using 'find_package_multi'
    """

    conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake, CMakeToolchain, CMakeToolchainBuildHelper

        class App(ConanFile):
            name = "app"
            version = "version"
            settings = "os", "arch", "compiler", "build_type"
            exports = "*.cpp", "*.txt"
            generators = "cmake_find_package_multi"

            def toolchain(self):
                tc = CMakeToolchain(self)
                tc.definitions["DEFINITIONS_BOTH"] = True
                tc.definitions.debug["DEFINITIONS_DEBUG"] = True
                tc.definitions.debug["DEFINITIONS_VALUE"] = "Debug"
                tc.definitions.release["DEFINITIONS_RELEASE"] = True
                tc.definitions.release["DEFINITIONS_VALUE"] = "Release"
                return tc

            def build(self):
                # A build helper could be easily added to replace these two lines
                # self.run('cmake "%s" -DCMAKE_TOOLCHAIN_FILE=""" + CMakeToolchain.filename + """' % (self.source_folder))
                # command_str = "cmake --build ."
                # if CMake(self).is_multi_configuration:
                #     command_str += " --config {}".format(str(self.settings.build_type))
                # self.run(command_str)

                cmake = CMakeToolchainBuildHelper(self)
                cmake.configure(source_folder=".")
                cmake.build()

            def package(self):
                if self.settings.compiler == "Visual Studio":
                    self.copy("{}/app.exe".format(self.settings.build_type), "", keep_path=False)
                else:
                    self.copy("app*", "", "", keep_path=False)
    """)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8)
        project(App CXX)
        
        if(NOT CMAKE_TOOLCHAIN_FILE)
            message(">> Not using toolchain")
            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()
        endif()

        message(">> CONAN_EXPORTED: ${CONAN_EXPORTED}")
        message(">> CONAN_IN_LOCAL_CACHE: ${CONAN_IN_LOCAL_CACHE}")
        
        message(">> DEFINITIONS_BOTH: ${DEFINITIONS_BOTH}")
        message(">> DEFINITIONS_DEBUG: ${DEFINITIONS_DEBUG}")
        message(">> DEFINITIONS_RELEASE: ${DEFINITIONS_RELEASE}")
        message(">> DEFINITIONS_VALUE: ${DEFINITIONS_VALUE}")
        
        add_executable(app src/app.cpp)
        target_compile_definitions(app PRIVATE DEFINITIONS_BOTH="${DEFINITIONS_BOTH}")
        target_compile_definitions(app PRIVATE DEFINITIONS_DEBUG=${DEFINITIONS_DEBUG})
        target_compile_definitions(app PRIVATE DEFINITIONS_RELEASE=${DEFINITIONS_RELEASE})
        target_compile_definitions(app PRIVATE DEFINITIONS_VALUE=${DEFINITIONS_VALUE})
        
    """)

    app_cpp = textwrap.dedent("""
        #include <iostream>

        int main() {
            std::cout << "DEFINITIONS_BOTH: " << DEFINITIONS_BOTH << "\\n";
            std::cout << "DEFINITIONS_DEBUG: " << DEFINITIONS_DEBUG << "\\n";
            std::cout << "DEFINITIONS_RELEASE: " << DEFINITIONS_RELEASE << "\\n";
            std::cout << "DEFINITIONS_VALUE: " << DEFINITIONS_VALUE << "\\n";
            return 0;
        }
    """)

    @classmethod
    def setUpClass(cls):
        # This is intended as a classmethod, this way the client will use the `CMakeCache` between
        #   builds and it will be testing that the toolchain initializes all the variables
        #   properly (it doesn't use preexisting data)
        cls.t = TurboTestClient(path_with_spaces=False)

        # Prepare the actual consumer package
        cls.t.save({"conanfile.py": cls.conanfile,
                    "CMakeLists.txt": cls.cmakelist,
                    "src/app.cpp": cls.app_cpp})
        cls.app_ref = ConanFileReference.loads("app/version@user/channel")

    @parameterized.expand([("Debug",), ("Release",)])
    def test_cache_create(self, build_type):
        # TODO: Remove? ...It is here just to check that the package builds in the cache
        # Compile the app in the cache
        pref = self.t.create(ref=self.app_ref, conanfile=self.conanfile,
                             args=" -s build_type={}".format(build_type))
        self.assertIn("Using Conan toolchain", self.t.out)
        self.assertIn(">> DEFINITIONS_BOTH: True", self.t.out)
        # per-config definitions are not resolved during configure
        self.assertIn('>> DEFINITIONS_DEBUG: $<IF:$', self.t.out)
        self.assertIn('>> DEFINITIONS_RELEASE: $<IF:$', self.t.out)
        self.assertIn('>> DEFINITIONS_VALUE: $<IF:$', self.t.out)

        # TODO: Remove these printing
        build_folder = self.t.cache.package_layout(pref.ref).build(pref)
        print("*"*200)
        print(load(os.path.join(build_folder, "conan_project_include.cmake")))
        print("!"*200)

        # Run the app and check it has been properly compiled
        package_layout = self.t.cache.package_layout(pref.ref)
        app_str = "app.exe" if platform.system() == "Windows" else "./app"
        self.t.run_command(app_str, cwd=package_layout.package(pref))
        # per-config definitions are resolved in build
        self.assertIn('DEFINITIONS_DEBUG: {}'.format("True" if build_type == "Debug" else ""), self.t.out)
        self.assertIn('DEFINITIONS_RELEASE: {}'.format("True" if build_type == "Release" else ""), self.t.out)
        self.assertIn('DEFINITIONS_VALUE: {}'.format(build_type), self.t.out)

    @parameterized.expand([("Debug",), ("Release",)])
    def test_local_conan(self, build_type):
        # TODO: Remove? ...Here just to check another way of building
        # Conan local workflow
        build_directory = os.path.join(self.t.current_folder, 'build')
        rmdir(build_directory)
        with self.t.chdir(build_directory):
            self.t.run("install .. -s build_type={}".format(build_type))
            self.t.run("build ..")
        self.assertIn("Using Conan toolchain", self.t.out)
        self.assertIn(">> DEFINITIONS_BOTH: True", self.t.out)
        # per-config definitions are not resolved during configure
        self.assertIn('>> DEFINITIONS_DEBUG: $<IF:$', self.t.out)
        self.assertIn('>> DEFINITIONS_RELEASE: $<IF:$', self.t.out)
        self.assertIn('>> DEFINITIONS_VALUE: $<IF:$', self.t.out)

        # Run the app and check it has been properly compiled
        command_str = "build\\{}\\app.exe".format(
            build_type) if platform.system() == "Windows" else "./build/app"
        self.t.run_command(command_str)
        # per-config definitions are resolved in build
        self.assertIn('DEFINITIONS_DEBUG: {}'.format("True" if build_type == "Debug" else ""), self.t.out)
        self.assertIn('DEFINITIONS_RELEASE: {}'.format("True" if build_type == "Release" else ""), self.t.out)
        self.assertIn('DEFINITIONS_VALUE: {}'.format(build_type), self.t.out)

    @unittest.skipUnless(platform.system() in ["Windows", "Darwin"], "Require multiconfig generator")
    def test_multiconfig_generator(self):
        build_directory = os.path.join(self.t.current_folder, 'build')
        rmdir(build_directory)
        with self.t.chdir(build_directory):
            self.t.run("install .. -s build_type=Debug")
            self.t.run("install .. -s build_type=Release")

            # Configure once
            mgenerator = "Xcode" if platform.system() == "Darwin" else "Visual Studio 16 2019"
            with environment_append({"CMAKE_GENERATOR": mgenerator}):
                cmake_configure = 'cmake .. -DCMAKE_TOOLCHAIN_FILE={}'.format(
                    CMakeToolchain.filename)
                self.t.run_command(cmake_configure)
            self.assertIn("Using Conan toolchain", self.t.out)
            self.assertIn(">> DEFINITIONS_BOTH: True", self.t.out)
            # per-config definitions are not resolved during configure
            self.assertIn('>> DEFINITIONS_DEBUG: $<IF:$', self.t.out)
            self.assertIn('>> DEFINITIONS_RELEASE: $<IF:$', self.t.out)
            self.assertIn('>> DEFINITIONS_VALUE: $<IF:$', self.t.out)

            # Test debug
            self.t.run_command("cmake --build . --config Debug")
            command_str = "Debug\\app.exe" if platform.system() == "Windows" else "./Debug/app"
            self.t.run_command(command_str)
            # per-config definitions are resolved in build
            self.assertIn('DEFINITIONS_DEBUG: True', self.t.out)
            self.assertIn('DEFINITIONS_RELEASE: ', self.t.out)
            self.assertIn('DEFINITIONS_VALUE: Debug', self.t.out)

            # Test release
            self.t.run_command("cmake --build . --config Release")
            command_str = "Release\\app.exe" if platform.system() == "Windows" else "./Release/app"
            self.t.run_command(command_str)
            # per-config definitions are resolved in build
            self.assertIn('DEFINITIONS_DEBUG: ', self.t.out)
            self.assertIn('DEFINITIONS_RELEASE: True', self.t.out)
            self.assertIn('DEFINITIONS_VALUE: Release', self.t.out)
