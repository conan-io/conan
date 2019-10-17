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


def compile_local_workflow(testcase, client, profile):
    # Conan local workflow
    with client.chdir("build"):
        client.run("install .. --profile={}".format(profile))
        client.run("build ..")
        testcase.assertIn("Using Conan toolchain", client.out)

    cmake_cache = load(os.path.join(client.current_folder, "build", "CMakeCache.txt"))
    return client.out, cmake_cache


def _compile_cache_workflow(testcase, client, profile, use_toolchain):
    # Compile the app in the cache
    pref = client.create(ref=ConanFileReference.loads("app/version@user/channel"), conanfile=None,
                         args=" --profile={} -o use_toolchain={}".format(profile, use_toolchain))
    if use_toolchain:
        testcase.assertIn("Using Conan toolchain", client.out)
    print(client.out)

    # Run the app and check it has been properly compiled
    package_layout = client.cache.package_layout(pref.ref)
    cmake_cache = load(os.path.join(package_layout.build(pref), "CMakeCache.txt"))
    return client.out, cmake_cache


def compile_cache_workflow_with_toolchain(testcase, client, profile):
    return _compile_cache_workflow(testcase, client, profile, use_toolchain=True)


def compile_cache_workflow_without_toolchain(testcase, client, profile):
    return _compile_cache_workflow(testcase, client, profile, use_toolchain=False)


def compile_cmake_workflow(testcase, client, profile):
    with client.chdir("build"):
        client.run("install .. --profile={}".format(profile))
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE={}".format(CMakeToolchain.filename))
        testcase.assertIn("Using Conan toolchain", client.out)

    cmake_cache = load(os.path.join(client.current_folder, "build", "CMakeCache.txt"))
    return client.out, cmake_cache


@parameterized_class([{"function": compile_cache_workflow_without_toolchain},
                      {"function": compile_cache_workflow_with_toolchain},
                      {"function": compile_local_workflow},
                      {"function": compile_cmake_workflow},
                      ])
@attr("toolchain")
class AdjustAutoTestCase(unittest.TestCase):
    """
        Check that it works adjusting values from the toolchain file
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

            def toolchain(self):
                tc = CMakeToolchain(self)
                return tc

            def build(self):
                # Do not actually build, just configure
                if self.options.use_toolchain:
                    # A build helper could be easily added to replace this line
                    self.run('cmake "%s" -DCMAKE_TOOLCHAIN_FILE=""" + CMakeToolchain.filename + """' % (self.source_folder))
                else:
                    cmake = CMake(self)
                    cmake.configure(source_folder=".")
    """)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8)
        project(App CXX)

        add_executable(app src/app.cpp)
    """)

    app_cpp = textwrap.dedent("""
        #include <iostream>

        int main() {
            return 0;
        }
    """)

    @classmethod
    def setUpClass(cls):
        cls.t = TurboTestClient(path_with_spaces=False)

        # Prepare the actual consumer package
        cls.t.save({"conanfile.py": cls.conanfile,
                    "CMakeLists.txt": cls.cmakelist,
                    "src/app.cpp": cls.app_cpp})
        # TODO: Remove the app.cpp and the add_executable, probably it is not need to run cmake configure.

    def _profile(self, client, settings_dict):
        settings_lines = "\n".join("{}={}".format(k, v) for k, v in settings_dict.items())
        profile = textwrap.dedent("""
            include(default)
            [settings]
            {}
        """.format(settings_lines))
        client.save({"profile": profile})
        return os.path.join(client.current_folder, "profile")

    @parameterized.expand([("Debug",), ("Release",)])
    def test_build_type(self, build_type):
        profile = self._profile(self.t, {"build_type": build_type})
        configure_out, cmake_cache = self.function(client=self.t, profile=profile)

        print(configure_out)
        print("*"*200)
        print(cmake_cache)

        # Contents of the CMakeCache
        self.assertIn("CMAKE_BUILD_TYPE:STRING={}".format(build_type), cmake_cache)



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
