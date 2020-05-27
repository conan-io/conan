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

from conans.util.runners import detect_runner
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
@unittest.skipUnless(platform.system() == "Linux", "Only linux")
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

    def _compiler_version_full(self, compiler, compiler_version):
        _, output = detect_runner("{}-{} --version".format(compiler, compiler_version))
        output = str(output) if six.PY2 else output
        line = output.splitlines()[0] if six.PY2 else output.split('\\n')[0]
        m = re.match(r".*\s(?P<version>\d+\.\d+\.\d+)", line)
        if not m:
            self.fail("Cannot find version in line '{}'".format(line))
        return m.group("version")

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

    @parameterized.expand([("5",), ("8",), ])
    def test_compiler_version_linux(self, compiler_version):
        if not self.use_toolchain:
            self.skipTest("It doesn't work without toolchain")

        if _running_ci and compiler_version == "8":
            self.skipTest("GCC 8 not available in Jenkins")

        cache_filepath = os.path.join(self.t.current_folder, "build", "CMakeCache.txt")
        if os.path.exists(cache_filepath):
            os.unlink(cache_filepath)  # FIXME: Ideally this shouldn't be needed (I need it only here)

        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"compiler.version": compiler_version})

        full_version_str = self._compiler_version_full("gcc", compiler_version)
        self.assertTrue(full_version_str.startswith(compiler_version))
        self.assertIn("-- The C compiler identification is GNU {}".format(full_version_str), configure_out)
        self.assertIn("-- The CXX compiler identification is GNU {}".format(full_version_str), configure_out)
        self.assertIn("-- Check for working C compiler: /usr/bin/gcc-{} -- works".format(compiler_version), configure_out)
        self.assertIn("-- Check for working CXX compiler: /usr/bin/g++-{} -- works".format(compiler_version), configure_out)

        self.assertEqual("/usr/bin/gcc-ar-{}".format(compiler_version), cmake_cache["CMAKE_CXX_COMPILER_AR:FILEPATH"])
        self.assertEqual("/usr/bin/gcc-ranlib-{}".format(compiler_version), cmake_cache["CMAKE_CXX_COMPILER_RANLIB:FILEPATH"])
        self.assertEqual("/usr/bin/gcc-ar-{}".format(compiler_version), cmake_cache["CMAKE_C_COMPILER_AR:FILEPATH"])
        self.assertEqual("/usr/bin/gcc-ranlib-{}".format(compiler_version), cmake_cache["CMAKE_C_COMPILER_RANLIB:FILEPATH"])

    @parameterized.expand([("gcc", "5", ), ("clang", "6.0"), ])
    def test_compiler_linux(self, compiler, compiler_version):
        if not self.use_toolchain:
            self.skipTest("It doesn't work without toolchain")

        if _running_ci and compiler == "clang":
            self.skipTest("Clang not available in Jenkins")

        cache_filepath = os.path.join(self.t.current_folder, "build", "CMakeCache.txt")
        if os.path.exists(cache_filepath):
            os.unlink(cache_filepath)  # FIXME: Ideally this shouldn't be needed (I need it only here)

        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"compiler": compiler,
                                                                                  "compiler.version": compiler_version})

        id_str = "GNU" if compiler == "gcc" else "Clang"
        cxx_compiler = "g++" if compiler == "gcc" else "clang++"
        full_version_str = self._compiler_version_full(compiler, compiler_version)
        self.assertTrue(full_version_str.startswith(compiler_version), "{} not starting with {}".format(full_version_str, compiler_version))
        self.assertIn("-- The C compiler identification is {} {}".format(id_str, full_version_str), configure_out)
        self.assertIn("-- The CXX compiler identification is {} {}".format(id_str, full_version_str), configure_out)
        self.assertIn("-- Check for working C compiler: /usr/bin/{}-{} -- works".format(compiler, compiler_version), configure_out)
        self.assertIn("-- Check for working CXX compiler: /usr/bin/{}-{} -- works".format(cxx_compiler, compiler_version), configure_out)

        tools_str = "gcc" if compiler == "gcc" else "llvm"
        self.assertEqual("/usr/bin/{}-ar-{}".format(tools_str, compiler_version), cmake_cache["CMAKE_CXX_COMPILER_AR:FILEPATH"])
        self.assertEqual("/usr/bin/{}-ranlib-{}".format(tools_str, compiler_version), cmake_cache["CMAKE_CXX_COMPILER_RANLIB:FILEPATH"])
        self.assertEqual("/usr/bin/{}-ar-{}".format(tools_str, compiler_version), cmake_cache["CMAKE_C_COMPILER_AR:FILEPATH"])
        self.assertEqual("/usr/bin/{}-ranlib-{}".format(tools_str, compiler_version), cmake_cache["CMAKE_C_COMPILER_RANLIB:FILEPATH"])
