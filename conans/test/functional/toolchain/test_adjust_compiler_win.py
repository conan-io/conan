# coding=utf-8

import os
import platform
import re
import textwrap
import unittest

import six
from jinja2 import Template
from nose.plugins.attrib import attr
from parameterized.parameterized import parameterized
from parameterized.parameterized import parameterized_class

from conans.client.tools import environment_append
from conans.test.utils.tools import TurboTestClient
from conans.test.functional.toolchain.builds import compile_cache_workflow_without_toolchain, \
    compile_cache_workflow_with_toolchain, compile_local_workflow, compile_cmake_workflow

_running_ci = 'JOB_NAME' in os.environ


@parameterized_class([{"function": compile_cache_workflow_without_toolchain, "use_toolchain": False,
                       "in_cache": True},
                      {"function": compile_cache_workflow_with_toolchain, "use_toolchain": True,
                       "in_cache": True},
                      {"function": compile_local_workflow, "use_toolchain": True, "in_cache": False},
                      {"function": compile_cmake_workflow, "use_toolchain": True, "in_cache": False},
                      ])
@attr("toolchain")
@unittest.skipUnless(platform.system() == "Windows", "Only Windows")
class AdjustAutoTestCase(unittest.TestCase):
    """
        Check that it works adjusting values from the toolchain file
    """

    _conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake, CMakeToolchain

        class App(ConanFile):
            name = "app"
            version = "version"
            settings = "os", "arch", "compiler", "build_type"
            exports = "*.cpp", "*.txt"
            generators = {% if use_toolchain %}"cmake_find_package"{% else %}"cmake"{% endif %}
            options = {"use_toolchain": [True, False], "fPIC": [True, False]}
            default_options = {"use_toolchain": True,
                               "fPIC": False}

            {% if use_toolchain %}
            def toolchain(self):
                tc = CMakeToolchain(self)
                return tc
            {% endif %}

            def build(self):
                # Do not actually build, just configure
                cmake = CMake(self)
                cmake.configure(source_folder=".")
    """)
    conanfile_toolchain = Template(_conanfile).render(use_toolchain=True)
    conanfile_no_toolchain = Template(_conanfile).render(use_toolchain=False)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8)
        project(App C CXX)

        if(CONAN_TOOLCHAIN_INCLUDED AND CMAKE_VERSION VERSION_LESS "3.15")
            include("${CMAKE_BINARY_DIR}/conan_project_include.cmake")
        endif()

        if(NOT CMAKE_TOOLCHAIN_FILE)
            message(">> Not using toolchain")
            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()
        endif()

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

        get_directory_property(_COMPILE_DEFINITONS DIRECTORY ${CMAKE_SOURCE_DIR} COMPILE_DEFINITIONS)
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
        conanfile = cls.conanfile_toolchain if cls.use_toolchain else cls.conanfile_no_toolchain
        cls.t.save({"conanfile.py": conanfile,
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
        return configure_out, cmake_cache_items, cmake_cache_keys, build_directory, package_directory

    def assertRegexIn(self, expr, iterable, msg=None):
        for item in iterable:
            try:
                six.assertRegex(self, item, expr)
            except AssertionError:
                pass
            else:
                return
        else:
            standard_msg = '%s not found in:\n %s' % (unittest.util.safe_repr(expr), "\n".join(iterable))
            self.fail(self._formatMessage(msg, standard_msg))

    @parameterized.expand([("15", "Visual Studio 15 2017"), ("16", "Visual Studio 16 2019"), ])
    def test_compiler_version_win(self, compiler_version, compiler_name):
        if not self.use_toolchain:
            self.skipTest("It doesn't work without toolchain")

        if _running_ci and compiler_version == "16":
            self.skipTest("VS 2019 not available in Jenkins")

        cache_filepath = os.path.join(self.t.current_folder, "build", "CMakeCache.txt")
        if os.path.exists(cache_filepath):
            os.unlink(cache_filepath)  # FIXME: Ideally this shouldn't be needed (I need it only here)

        with environment_append({"CMAKE_GENERATOR": compiler_name}):  # TODO: FIXME: The toolchain needs an environment
            configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure(
                {"compiler.version": compiler_version})

        self.assertIn("-- Building for: {}".format(compiler_name), configure_out)
        if compiler_version == "15":
            self.assertRegexIn(r"-- The C compiler identification is MSVC 19\.16\.270\d{2}\.\d", configure_out)
            self.assertRegexIn(r"-- The CXX compiler identification is MSVC 19\.16\.270\d{2}\.\d", configure_out)
            self.assertRegexIn(r"-- Check for working C compiler: C:\/Program Files \(x86\)\/"
                               r"Microsoft Visual Studio\/2017\/(BuildTools|Community)\/VC\/Tools\/"
                               r"MSVC\/14\.16\.27023\/bin\/Hostx86\/x64\/cl\.exe -- works", configure_out)
            self.assertRegexIn(r"-- Check for working CXX compiler: C:\/Program Files \(x86\)\/"
                               r"Microsoft Visual Studio\/2017\/(BuildTools|Community)\/VC\/Tools\/"
                               r"MSVC\/14\.16\.27023\/bin\/Hostx86\/x64\/cl\.exe -- works", configure_out)
        else:
            self.assertRegexIn(r"-- The C compiler identification is MSVC 19\.24\.28314\.0", configure_out)
            self.assertRegexIn(r"-- The CXX compiler identification is MSVC 19\.24\.28314\.0", configure_out)
            self.assertRegexIn(r"-- Check for working C compiler: C:\/Program Files \(x86\)\/"
                               r"Microsoft Visual Studio\/2019\/Community\/VC\/Tools\/"
                               r"MSVC\/14\.24\.28314\/bin\/Hostx64\/x64\/cl\.exe -- works", configure_out)
            self.assertRegexIn(r"-- Check for working CXX compiler: C:\/Program Files \(x86\)/"
                               r"Microsoft Visual Studio\/2019\/Community\/VC\/Tools\/"
                               r"MSVC\/14\.24\.28314\/bin\/Hostx64\/x64\/cl\.exe -- works", configure_out)

        self.assertEqual(compiler_name, cmake_cache["CMAKE_GENERATOR:INTERNAL"])

    @parameterized.expand([("v140",), ("v141",), ("v142",), ])
    def test_compiler_toolset_win(self, compiler_toolset):
        if _running_ci and compiler_toolset == "v142":
            self.skipTest("Toolset v142 is not available in Jenkins")

        # TODO: What if the toolset is not installed for the CMAKE_GENERATOR given?

        cache_filepath = os.path.join(self.t.current_folder, "build", "CMakeCache.txt")
        if os.path.exists(cache_filepath):
            os.unlink(cache_filepath)  # FIXME: Remove, I'm already deleting the 'build' folder

        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"compiler.toolset": compiler_toolset})

        # self.assertIn("compiler.toolset={}".format(compiler_toolset), configure_out)
        # self.assertIn("-- Building for: Visual Studio 16 2019", configure_out)
        if compiler_toolset == "v140":
            self.assertRegexIn(r"-- The C compiler identification is MSVC 19\.0\.242\d{2}\.\d", configure_out)
            self.assertRegexIn(r"-- The CXX compiler identification is MSVC 19\.0\.242\d{2}\.\d", configure_out)
            self.assertRegexIn(r"-- Check for working C compiler: C:\/Program Files \(x86\)\/"
                               r"Microsoft Visual Studio 14\.0\/VC\/bin\/(x86_)?amd64\/cl\.exe -- works", configure_out)
            self.assertRegexIn(r"-- Check for working CXX compiler: C:\/Program Files \(x86\)\/"
                               r"Microsoft Visual Studio 14\.0\/VC\/bin\/(x86_)?amd64\/cl\.exe -- works", configure_out)
        elif compiler_toolset == "v141":
            self.assertRegexIn(r"-- The C compiler identification is MSVC 19\.16\.270\d{2}\.\d", configure_out)
            self.assertRegexIn(r"-- The CXX compiler identification is MSVC 19\.16\.270\d{2}\.\d", configure_out)
            self.assertRegexIn(r"-- Check for working C compiler: C:\/Program Files \(x86\)\/"
                               r"Microsoft Visual Studio\/(2017\/BuildTools|2019\/Community)\/VC\/Tools\/"
                               r"MSVC\/14\.16\.27023\/bin\/Host(x86|X64)\/x64\/cl\.exe -- works", configure_out)
            self.assertRegexIn(r"-- Check for working CXX compiler: C:\/Program Files \(x86\)\/"
                               r"Microsoft Visual Studio\/(2017\/BuildTools|2019\/Community)\/VC\/Tools\/"
                               r"MSVC\/14\.16\.27023\/bin\/Host(x86|X64)\/x64\/cl\.exe -- works", configure_out)
        else:
            self.assertRegexIn(r"-- The C compiler identification is MSVC 19\.24\.28314\.0", configure_out)
            self.assertRegexIn(r"-- The CXX compiler identification is MSVC 19\.24\.28314\.0", configure_out)
            self.assertRegexIn(r"-- Check for working C compiler: C:\/Program Files \(x86\)\/"
                               r"Microsoft Visual Studio\/2019\/Community\/VC\/Tools\/"
                               r"MSVC\/14\.24\.28314\/bin\/Hostx64\/x64\/cl\.exe -- works", configure_out)
            self.assertRegexIn(r"-- Check for working CXX compiler: C:\/Program Files \(x86\)\/"
                               r"Microsoft Visual Studio\/2019\/Community\/VC\/Tools\/"
                               r"MSVC\/14\.24\.28314\/bin\/Hostx64\/x64\/cl\.exe -- works", configure_out)

        if compiler_toolset == "v140":
            six.assertRegex(self, cmake_cache["CMAKE_LINKER:FILEPATH"],
                            r"C:\/Program Files \(x86\)\/Microsoft Visual Studio 14\.0\/VC\/"
                            r"bin\/(x86_)?amd64\/link\.exe")
        elif compiler_toolset == "v141":
            six.assertRegex(self, cmake_cache["CMAKE_LINKER:FILEPATH"],
                            r"C:\/Program Files \(x86\)\/Microsoft Visual Studio\/(2017\/BuildTools|2019\/Community)\/"
                            r"VC\/Tools\/MSVC\/14\.16\.27023\/bin\/Host(x86|X64)\/x64\/link\.exe")
        else:
            self.assertEqual("C:/Program Files (x86)/Microsoft Visual Studio/2019/Community/VC/Tools/"
                             "MSVC/14.24.28314/bin/Hostx64/x64/link.exe", cmake_cache["CMAKE_LINKER:FILEPATH"])
