# coding=utf-8

import os
import platform
import re
import textwrap
import unittest

from nose.plugins.attrib import attr
from parameterized.parameterized import parameterized
from parameterized.parameterized import parameterized_class

from conans.client.toolchain.cmake import CMakeToolchain
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TurboTestClient
from conans.util.files import load


def compile_local_workflow(testcase, client, profile):
    # Conan local workflow
    with client.chdir("build"):
        client.run("install .. --profile={}".format(profile))
        client.run("build ..")
        testcase.assertIn("Using Conan toolchain", client.out)

    build_directory = os.path.join(client.current_folder, "build")
    cmake_cache = load(os.path.join(build_directory, "CMakeCache.txt"))
    if True:
        # TODO: Remove
        toolcahin = load(os.path.join(build_directory, CMakeToolchain.filename))
        print(toolcahin)
        print("!" * 200)
    return client.out, cmake_cache, build_directory, None


def _compile_cache_workflow(testcase, client, profile, use_toolchain):
    # Compile the app in the cache
    pref = client.create(ref=ConanFileReference.loads("app/version@user/channel"), conanfile=None,
                         args=" --profile={} -o use_toolchain={}".format(profile, use_toolchain))
    if use_toolchain:
        testcase.assertIn("Using Conan toolchain", client.out)

    package_layout = client.cache.package_layout(pref.ref)
    build_directory = package_layout.build(pref)
    cmake_cache = load(os.path.join(build_directory, "CMakeCache.txt"))

    if use_toolchain:
        # TODO: Remove
        toolcahin = load(os.path.join(build_directory, CMakeToolchain.filename))
        print(toolcahin)
        print("!" * 200)
    return client.out, cmake_cache, build_directory, package_layout.package(pref)


def compile_cache_workflow_with_toolchain(testcase, client, profile):
    return _compile_cache_workflow(testcase, client, profile, use_toolchain=True)


def compile_cache_workflow_without_toolchain(testcase, client, profile):
    return _compile_cache_workflow(testcase, client, profile, use_toolchain=False)


def compile_cmake_workflow(testcase, client, profile):
    with client.chdir("build"):
        client.run("install .. --profile={}".format(profile))
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE={}".format(CMakeToolchain.filename))
        testcase.assertIn("Using Conan toolchain", client.out)

    build_directory = os.path.join(client.current_folder, "build")
    cmake_cache = load(os.path.join(build_directory, "CMakeCache.txt"))
    if True:
        # TODO: Remove
        toolcahin = load(os.path.join(build_directory, CMakeToolchain.filename))
        print(toolcahin)
        print("!" * 200)
    return client.out, cmake_cache, build_directory, None


@parameterized_class([{"function": compile_cache_workflow_without_toolchain, "use_toolchain": False,
                       "in_cache": True},
                      {"function": compile_cache_workflow_with_toolchain, "use_toolchain": True,
                       "in_cache": True},
                      {"function": compile_local_workflow, "use_toolchain": True, "in_cache": False},
                      {"function": compile_cmake_workflow, "use_toolchain": True, "in_cache": False},
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
            options = {"use_toolchain": [True, False], "fPIC": [True, False]}
            default_options = {"use_toolchain": True,
                               "fPIC": False}

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
        project(App C CXX)

        if(NOT CMAKE_TOOLCHAIN_FILE)
            message(">> Not using toolchain")
            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()
        endif()

        message(">> CONAN_EXPORTED: ${CONAN_EXPORTED}")
        message(">> CONAN_IN_LOCAL_CACHE: ${CONAN_IN_LOCAL_CACHE}")

        message(">> CMAKE_BUILD_TYPE: ${CMAKE_BUILD_TYPE}")
        message(">> CMAKE_CXX_FLAGS: ${CMAKE_CXX_FLAGS}")
        message(">> CMAKE_CXX_FLAGS_DEBUG: ${CMAKE_CXX_FLAGS_DEBUG}")
        message(">> CMAKE_CXX_FLAGS_RELEASE: ${CMAKE_CXX_FLAGS_RELEASE}")
        message(">> CMAKE_C_FLAGS: ${CMAKE_C_FLAGS}")
        message(">> CMAKE_C_FLAGS_DEBUG: ${CMAKE_C_FLAGS_DEBUG}")
        message(">> CMAKE_C_FLAGS_RELEASE: ${CMAKE_C_FLAGS_RELEASE}")
        message(">> CMAKE_SHARED_LINKER_FLAGS: ${CMAKE_SHARED_LINKER_FLAGS}")
        message(">> CMAKE_EXE_LINKER_FLAGS: ${CMAKE_EXE_LINKER_FLAGS}")

        message(">> CMAKE_CXX_STANDARD: ${CMAKE_CXX_STANDARD}")
        message(">> CMAKE_CXX_EXTENSIONS: ${CMAKE_CXX_EXTENSIONS}")

        message(">> CMAKE_INSTALL_BINDIR: ${CMAKE_INSTALL_BINDIR}")
        message(">> CMAKE_INSTALL_DATAROOTDIR: ${CMAKE_INSTALL_DATAROOTDIR}")
        message(">> CMAKE_INSTALL_INCLUDEDIR: ${CMAKE_INSTALL_INCLUDEDIR}")
        message(">> CMAKE_INSTALL_LIBDIR: ${CMAKE_INSTALL_LIBDIR}")
        message(">> CMAKE_INSTALL_LIBEXECDIR: ${CMAKE_INSTALL_LIBEXECDIR}")
        message(">> CMAKE_INSTALL_OLDINCLUDEDIR: ${CMAKE_INSTALL_OLDINCLUDEDIR}")
        message(">> CMAKE_INSTALL_SBINDIR: ${CMAKE_INSTALL_SBINDIR}")
        message(">> CMAKE_INSTALL_PREFIX: ${CMAKE_INSTALL_PREFIX}")

        message(">> CMAKE_POSITION_INDEPENDENT_CODE: ${CMAKE_POSITION_INDEPENDENT_CODE}")

        message(">> CMAKE_INSTALL_NAME_DIR: ${CMAKE_INSTALL_NAME_DIR}")
        message(">> CMAKE_SKIP_RPATH: ${CMAKE_SKIP_RPATH}")

        message(">> CMAKE_MODULE_PATH: ${CMAKE_MODULE_PATH}")
        message(">> CMAKE_PREFIX_PATH: ${CMAKE_PREFIX_PATH}")

        message(">> CMAKE_INCLUDE_PATH: ${CMAKE_INCLUDE_PATH}")
        message(">> CMAKE_LIBRARY_PATH: ${CMAKE_LIBRARY_PATH}")

        add_executable(app src/app.cpp)

        get_directory_property(_COMPILE_DEFINITONS DIRECTORY ${CMAKE_SOURCE_DIR} COMPILE_DEFINITIONS )
        message(">> COMPILE_DEFINITONS: ${_COMPILE_DEFINITONS}")
    """)

    app_cpp = textwrap.dedent("""
        #include <iostream>

        int main() {
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
        # TODO: Remove the app.cpp and the add_executable, probably it is not need to run cmake configure.

    def _run_configure(self, settings_dict=None, options_dict=None):
        # Build the profile according to the settings provided
        settings_lines = "\n".join(
            "{}={}".format(k, v) for k, v in settings_dict.items()) if settings_dict else ""
        options_lines = "\n".join(
            "{}={}".format(k, v) for k, v in options_dict.items()) if options_dict else ""
        profile = textwrap.dedent("""
                    include(default)
                    [settings]
                    {}
                    [options]
                    {}
                """.format(settings_lines, options_lines))
        self.t.save({"profile": profile})
        profile_path = os.path.join(self.t.current_folder, "profile").replace("\\", "/")

        # Run the configure corresponding to this test case
        configure_out, cmake_cache, build_directory, package_directory = self.function(client=self.t,
                                                                                       profile=profile_path)
        build_directory = build_directory.replace("\\", "/")
        if package_directory:
            package_directory = package_directory.replace("\\", "/")

        # Prepare the outputs for the test cases
        configure_out = [re.sub(r"\s\s+", " ", line) for line in str(
            configure_out).splitlines()]  # FIXME: There are some extra spaces between flags
        cmake_cache_items = {}
        for line in cmake_cache.splitlines():
            if not line.strip() or line.startswith("//") or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            cmake_cache_items[key] = value
        cmake_cache_keys = [item.split(":")[0] for item in cmake_cache_items.keys()]

        self._print_things(configure_out, cmake_cache_items)
        return configure_out, cmake_cache_items, cmake_cache_keys, build_directory, package_directory

    def _print_things(self, configure_out, cmake_cache):
        # TODO: Remove this functions
        print("\n".join(configure_out))
        print("*" * 200)
        from pprint import pprint
        pprint(cmake_cache)

    @parameterized.expand([("7",), ("8",), ])
    @unittest.skipUnless(platform.system() == "Linux", "Only linux")
    def test_compiler_version_linux(self, compiler_version):
        if not self.use_toolchain:
            self.skipTest("It doesn't work without toolchain")

        cache_filepath = os.path.join(self.t.current_folder, "build", "CMakeCache.txt")
        if os.path.exists(cache_filepath):
            os.unlink(cache_filepath)  # FIXME: Ideally this shouldn't be needed (I need it only here)

        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"compiler.version": compiler_version})

        def gcc_version_full():
            import re
            from conans.client.conf.detect import _execute
            _, output = _execute("gcc-{} --version".format(compiler_version))
            m = re.match(r".*(?P<version>\d\.\d\.\d)$", output.split("\\n")[0])
            return m.group("version")

        full_version_str = gcc_version_full()
        self.assertTrue(full_version_str.startswith(compiler_version))
        self.assertIn("-- The C compiler identification is GNU {}".format(full_version_str), configure_out)
        self.assertIn("-- The CXX compiler identification is GNU {}".format(full_version_str), configure_out)
        self.assertIn("-- Check for working C compiler: /usr/bin/gcc-{} -- works".format(compiler_version), configure_out)
        self.assertIn("-- Check for working CXX compiler: /usr/bin/g++-{} -- works".format(compiler_version), configure_out)

        self.assertEqual("/usr/bin/gcc-ar-{}".format(compiler_version), cmake_cache["CMAKE_CXX_COMPILER_AR:FILEPATH"])
        self.assertEqual("/usr/bin/gcc-ranlib-{}".format(compiler_version), cmake_cache["CMAKE_CXX_COMPILER_RANLIB:FILEPATH"])
        self.assertEqual("/usr/bin/gcc-ar-{}".format(compiler_version), cmake_cache["CMAKE_C_COMPILER_AR:FILEPATH"])
        self.assertEqual("/usr/bin/gcc-ranlib-{}".format(compiler_version), cmake_cache["CMAKE_C_COMPILER_RANLIB:FILEPATH"])

    @parameterized.expand([("gcc", "7", ), ("clang", "6.0"), ])
    @unittest.skipUnless(platform.system() == "Linux", "Only linux")
    def test_compiler_linux(self, compiler, compiler_version):
        if not self.use_toolchain:
            self.skipTest("It doesn't work without toolchain")

        cache_filepath = os.path.join(self.t.current_folder, "build", "CMakeCache.txt")
        if os.path.exists(cache_filepath):
            os.unlink(cache_filepath)  # FIXME: Ideally this shouldn't be needed (I need it only here)

        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"compiler": compiler,
                                                                                  "compiler.version": compiler_version})

        def gcc_version_full():
            import re
            from conans.client.conf.detect import _execute
            _, output = _execute("gcc-{} --version".format(compiler_version))
            m = re.match(r".*(?P<version>\d\.\d\.\d)$", output.split("\\n")[0])
            return m.group("version")

        id_str = "GNU" if compiler == "gcc" else "Clang"
        cxx_compiler = "g++" if compiler == "gcc" else "clang++"
        full_version_str = gcc_version_full() if compiler == "gcc" else "6.0.0"
        self.assertTrue(full_version_str.startswith(compiler_version))
        self.assertIn("-- The C compiler identification is {} {}".format(id_str, full_version_str), configure_out)
        self.assertIn("-- The CXX compiler identification is {} {}".format(id_str, full_version_str), configure_out)
        self.assertIn("-- Check for working C compiler: /usr/bin/{}-{} -- works".format(compiler, compiler_version), configure_out)
        self.assertIn("-- Check for working CXX compiler: /usr/bin/{}-{} -- works".format(cxx_compiler, compiler_version), configure_out)

        tools_str = "gcc" if compiler == "gcc" else "llvm"
        self.assertEqual("/usr/bin/{}-ar-{}".format(tools_str, compiler_version), cmake_cache["CMAKE_CXX_COMPILER_AR:FILEPATH"])
        self.assertEqual("/usr/bin/{}-ranlib-{}".format(tools_str, compiler_version), cmake_cache["CMAKE_CXX_COMPILER_RANLIB:FILEPATH"])
        self.assertEqual("/usr/bin/{}-ar-{}".format(tools_str, compiler_version), cmake_cache["CMAKE_C_COMPILER_AR:FILEPATH"])
        self.assertEqual("/usr/bin/{}-ranlib-{}".format(tools_str, compiler_version), cmake_cache["CMAKE_C_COMPILER_RANLIB:FILEPATH"])

    @parameterized.expand([("7",), ("8",), ])
    @unittest.skipUnless(platform.system() == "Windows", "Only Windows")
    def test_compiler_version_win(self, compiler_version):
        self.fail("Not implemented: different versions of Visual Studio")

    @parameterized.expand([("7",), ("8",), ])
    @unittest.skipUnless(platform.system() == "Windows", "Only Windows")
    def test_compiler_toolset_win(self, compiler_version):
        self.fail("Not implemented: different versions of Visual Studio toolset")
