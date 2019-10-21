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
        print("!"*200)
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
        print("!"*200)
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
        print("!"*200)
    return client.out, cmake_cache, build_directory, None


@parameterized_class([{"function": compile_cache_workflow_without_toolchain, "use_toolchain": False, "in_cache": True},
                      {"function": compile_cache_workflow_with_toolchain, "use_toolchain": True, "in_cache": True},
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
            message(">> Using toolchain")
            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()
        endif()

        message(">> CONAN_EXPORTED: ${CONAN_EXPORTED}")
        message(">> CONAN_IN_LOCAL_CACHE: ${CONAN_IN_LOCAL_CACHE}")

        message(">> CMAKE_BUILD_TYPE: ${CMAKE_BUILD_TYPE}")
        message(">> CMAKE_CXX_FLAGS: ${CMAKE_CXX_FLAGS}")
        message(">> CMAKE_C_FLAGS: ${CMAKE_C_FLAGS}")
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
        settings_lines = "\n".join("{}={}".format(k, v) for k, v in settings_dict.items()) if settings_dict else ""
        options_lines = "\n".join("{}={}".format(k, v) for k, v in options_dict.items()) if options_dict else ""
        profile = textwrap.dedent("""
                    include(default)
                    [settings]
                    {}
                    [options]
                    {}
                """.format(settings_lines, options_lines))
        self.t.save({"profile": profile})
        profile_path = os.path.join(self.t.current_folder, "profile")

        # Run the configure corresponding to this test case
        configure_out, cmake_cache, build_directory, package_directory = self.function(client=self.t, profile=profile_path)

        # Prepare the outputs for the test cases
        configure_out = [re.sub(r"\s\s+", " ", line) for line in str(configure_out).splitlines()]  # FIXME: There are some extra spaces between flags
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
        print("*"*200)
        from pprint import pprint
        pprint(cmake_cache)

    def test_conan_stuff(self):
        # self.skipTest("Disabled")
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure()

        in_local_cache = "ON" if self.in_cache else "OFF"
        exported_str = "1"
        if self.in_cache:
            self.assertIn(">> CONAN_EXPORTED: {}".format(exported_str), configure_out)
            self.assertIn(">> CONAN_IN_LOCAL_CACHE: {}".format(in_local_cache), configure_out)

            type_str = "STRING" if self.use_toolchain else "UNINITIALIZED"
            self.assertEqual(exported_str, cmake_cache["CONAN_EXPORTED:" + type_str])
            self.assertEqual(in_local_cache, cmake_cache["CONAN_IN_LOCAL_CACHE:" + type_str])
        else:
            self.assertIn(">> CONAN_EXPORTED: {}".format(exported_str), configure_out)
            self.assertIn(">> CONAN_IN_LOCAL_CACHE: {}".format(in_local_cache), configure_out)

            type_str = "STRING" if self.use_toolchain else "UNINITIALIZED"
            self.assertEqual(exported_str, cmake_cache["CONAN_EXPORTED:" + type_str])
            self.assertEqual(in_local_cache, cmake_cache["CONAN_IN_LOCAL_CACHE:" + type_str])

    @parameterized.expand([("Debug",), ("Release",)])
    def test_build_type(self, build_type):
        #self.skipTest("Disabled")
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"build_type": build_type})

        #self.assertIn("build_type={}".format(build_type), configure_out)
        self.assertIn(">> CMAKE_BUILD_TYPE: {}".format(build_type), configure_out)

        self.assertEqual(build_type, cmake_cache["CMAKE_BUILD_TYPE:STRING"])

    @parameterized.expand([("libc++",), ])  # ("libstdc++",), is deprecated
    @unittest.skipIf(platform.system() != "Darwin", "libcxx for Darwin")
    def test_libcxx(self, libcxx):
        #self.skipTest("Disabled")
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"compiler.libcxx": libcxx})

        #self.assertIn("compiler.libcxx={}".format(libcxx), configure_out)
        self.assertIn("-- Conan: C++ stdlib: {}".format(libcxx), configure_out)
        self.assertIn(">> CMAKE_CXX_FLAGS: -m64 -stdlib={}".format(libcxx), configure_out)

        if not self.use_toolchain:
            self.assertEqual(libcxx, cmake_cache["CONAN_LIBCXX:UNINITIALIZED"])
        else:
            self.assertEqual(libcxx, cmake_cache["CONAN_LIBCXX:STRING"])

    def test_install_paths(self):
        #self.skipTest("Disabled")
        configure_out, cmake_cache, cmake_cache_keys, _, package_dir = self._run_configure()

        value_f = lambda u: u if self.in_cache else ""
        self.assertIn(">> CMAKE_INSTALL_BINDIR: {}".format(value_f("bin")), configure_out)
        self.assertIn(">> CMAKE_INSTALL_DATAROOTDIR: {}".format(value_f("share")), configure_out)
        self.assertIn(">> CMAKE_INSTALL_INCLUDEDIR: {}".format(value_f("include")), configure_out)
        self.assertIn(">> CMAKE_INSTALL_LIBDIR: {}".format(value_f("lib")), configure_out)
        self.assertIn(">> CMAKE_INSTALL_LIBEXECDIR: {}".format(value_f("bin")), configure_out)
        self.assertIn(">> CMAKE_INSTALL_OLDINCLUDEDIR: {}".format(value_f("include")), configure_out)
        self.assertIn(">> CMAKE_INSTALL_SBINDIR: {}".format(value_f("bin")), configure_out)
        if self.in_cache:
            self.assertIn(">> CMAKE_INSTALL_PREFIX: {}".format(package_dir), configure_out)
        else:
            pass  # TODO: It takes the default value, override it to something?

        if self.in_cache:
            type_str = "STRING" if self.use_toolchain else "UNINITIALIZED"
            self.assertEqual("bin", cmake_cache["CMAKE_INSTALL_BINDIR:" + type_str])
            self.assertEqual("share", cmake_cache["CMAKE_INSTALL_DATAROOTDIR:" + type_str])
            self.assertEqual("include", cmake_cache["CMAKE_INSTALL_INCLUDEDIR:" + type_str])
            self.assertEqual("lib", cmake_cache["CMAKE_INSTALL_LIBDIR:" + type_str])
            self.assertEqual("bin", cmake_cache["CMAKE_INSTALL_LIBEXECDIR:" + type_str])
            self.assertEqual("include", cmake_cache["CMAKE_INSTALL_OLDINCLUDEDIR:" + type_str])
            self.assertEqual("bin", cmake_cache["CMAKE_INSTALL_SBINDIR:" + type_str])
            type_str = "STRING" if self.use_toolchain else "PATH"
            self.assertEqual(package_dir, cmake_cache["CMAKE_INSTALL_PREFIX:" + type_str])
        else:
            self.assertNotIn("CMAKE_INSTALL_BINDIR", cmake_cache_keys)
            self.assertNotIn("CMAKE_INSTALL_DATAROOTDIR", cmake_cache_keys)
            self.assertNotIn("CMAKE_INSTALL_INCLUDEDIR", cmake_cache_keys)
            self.assertNotIn("CMAKE_INSTALL_LIBDIR", cmake_cache_keys)
            self.assertNotIn("CMAKE_INSTALL_LIBEXECDIR", cmake_cache_keys)
            self.assertNotIn("CMAKE_INSTALL_OLDINCLUDEDIR", cmake_cache_keys)
            self.assertNotIn("CMAKE_INSTALL_SBINDIR", cmake_cache_keys)
            #self.assertNotIn("CMAKE_INSTALL_PREFIX", cmake_cache_keys)  # TODO: It takes the default value '/usr/local', override to?

    @unittest.skipIf(platform.system() != "Darwin", "Only MacOS")
    def test_ccxx_flags(self):
        #self.skipTest("Disabled")
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure()

        self.assertIn(">> CMAKE_CXX_FLAGS: -m64 -stdlib=libc++", configure_out)
        self.assertIn(">> CMAKE_C_FLAGS: -m64", configure_out)
        self.assertIn(">> CMAKE_SHARED_LINKER_FLAGS: -m64", configure_out)
        self.assertIn(">> CMAKE_EXE_LINKER_FLAGS: ", configure_out)

        if self.use_toolchain:
            self.assertEqual(" -m64 -stdlib=libc++", cmake_cache["CMAKE_CXX_FLAGS:STRING"])
            self.assertEqual(" -m64", cmake_cache["CMAKE_C_FLAGS:STRING"])
        else:
            # FIXME: Cache doesn't match those in CMakeLists
            self.assertEqual("", cmake_cache["CMAKE_CXX_FLAGS:STRING"])
            self.assertEqual("", cmake_cache["CMAKE_C_FLAGS:STRING"])

        self.assertEqual("", cmake_cache["CMAKE_SHARED_LINKER_FLAGS:STRING"])
        self.assertEqual("", cmake_cache["CMAKE_EXE_LINKER_FLAGS:STRING"])

    @parameterized.expand([("gnu14",), ("14", ), ])
    def test_stdcxx_flags(self, cppstd):
        #self.skipTest("Disabled")
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"compiler.cppstd": cppstd})

        extensions_str = "ON" if "gnu" in cppstd else "OFF"
        #self.assertIn("compiler.cppstd={}".format(cppstd), configure_out)
        self.assertIn("-- Conan setting CPP STANDARD: 14 WITH EXTENSIONS {}".format(extensions_str), configure_out)
        self.assertIn(">> CMAKE_CXX_STANDARD: 14", configure_out)
        self.assertIn(">> CMAKE_CXX_EXTENSIONS: {}".format(extensions_str), configure_out)

        # FIXME: Cache doesn't match those in CMakeLists
        self.assertNotIn("CMAKE_CXX_STANDARD", cmake_cache_keys)
        self.assertNotIn("CMAKE_CXX_EXTENSIONS", cmake_cache_keys)
        type_str = "STRING" if self.use_toolchain else "UNINITIALIZED"
        cxx_flag_str = "gnu++" if "gnu" in cppstd else "c++"
        self.assertEqual("-std={}14".format(cxx_flag_str), cmake_cache["CONAN_STD_CXX_FLAG:" + type_str])
        if self.use_toolchain:
            self.assertEqual(extensions_str, cmake_cache["CONAN_CMAKE_CXX_EXTENSIONS:STRING"])
            self.assertEqual("14", cmake_cache["CONAN_CMAKE_CXX_STANDARD:STRING"])

    @parameterized.expand([("True",), ("False", ), ])
    def test_fPIC(self, fpic):
        #self.skipTest("Disabled")
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure(options_dict={"app:fPIC": fpic})

        fpic_str = "ON" if fpic == "True" else "OFF"
        #self.assertIn("app:fPIC={}".format(fpic), configure_out)
        self.assertIn("-- Conan: Adjusting fPIC flag ({})".format(fpic_str), configure_out)
        self.assertIn(">> CMAKE_POSITION_INDEPENDENT_CODE: {}".format(fpic_str), configure_out)

        type_str = "STRING" if self.use_toolchain else "UNINITIALIZED"
        self.assertEqual(fpic_str, cmake_cache["CONAN_CMAKE_POSITION_INDEPENDENT_CODE:" + type_str])
        self.assertNotIn("CMAKE_POSITION_INDEPENDENT_CODE", cmake_cache_keys)

    @unittest.skipIf(platform.system() != "Darwin", "libcxx for Darwin")
    def test_rpath(self):
        #self.skipTest("Disabled")
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure()

        self.assertIn(">> CMAKE_INSTALL_NAME_DIR: ", configure_out)
        self.assertIn(">> CMAKE_SKIP_RPATH: 1", configure_out)

        if self.use_toolchain:
            self.assertEqual("1", cmake_cache["CMAKE_SKIP_RPATH:BOOL"])
        else:
            self.assertEqual("NO", cmake_cache["CMAKE_SKIP_RPATH:BOOL"])

    def test_find_paths(self):
        #self.skipTest("Disabled")
        configure_out, cmake_cache, cmake_cache_keys, build_directory, _ = self._run_configure()

        # TODO: CONAN_CMAKE_MODULE_PATH, we are not populating that variable! never?!

        self.assertIn(">> CMAKE_MODULE_PATH: {}".format(build_directory), configure_out)
        self.assertIn(">> CMAKE_PREFIX_PATH: ", configure_out)

        type_str = "STRING" if self.use_toolchain else "UNINITIALIZED"
        self.assertEqual(build_directory, cmake_cache["CMAKE_MODULE_PATH:" + type_str])
        self.assertNotIn("CMAKE_PREFIX_PATH", cmake_cache_keys)

    def test_find_library_paths(self):
        #self.skipTest("Disabled")
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure()

        self.assertIn(">> CMAKE_INCLUDE_PATH: ", configure_out)
        self.assertIn(">> CMAKE_LIBRARY_PATH: ", configure_out)

        self.assertNotIn("CMAKE_INCLUDE_PATH", cmake_cache_keys)
        self.assertNotIn("CMAKE_LIBRARY_PATH", cmake_cache_keys)

        # TODO: We need a test using dependencies
