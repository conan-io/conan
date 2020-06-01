# coding=utf-8

import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr
from parameterized.parameterized import parameterized

from conans.test.utils.tools import TestClient


@attr("toolchain")
class TestToolchain(unittest.TestCase):

    conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake, CMakeToolchain

        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1"
            generators = "cmake_find_package_multi"

            def toolchain(self):
                tc = CMakeToolchain(self)
                tc.definitions["DEFINITIONS_BOTH"] = True
                tc.definitions.debug["DEFINITIONS_CONFIG"] = "Debug"
                tc.definitions.release["DEFINITIONS_CONFIG"] = "Release"
                return tc

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)

    app = textwrap.dedent("""
        #include <iostream>
        #include "hello.h"

        int main() {
            std::cout << "Hello: " << HELLO_MSG <<std::endl;
            #ifdef NDEBUG
            std::cout << "App: Release!" <<std::endl;
            #else
            std::cout << "App: Debug!" <<std::endl;
            #endif
            std::cout << "DEFINITIONS_BOTH: " << DEFINITIONS_BOTH << "\\n";
            std::cout << "DEFINITIONS_CONFIG: " << DEFINITIONS_CONFIG << "\\n";
            return 0;
        }
        """)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8)
        project(App C CXX)

        if(CONAN_TOOLCHAIN_INCLUDED AND CMAKE_VERSION VERSION_LESS "3.15")
            include("${CMAKE_BINARY_DIR}/conan_project_include.cmake")
        endif()

        if(NOT CMAKE_TOOLCHAIN_FILE)
            message(FATAL ">> Not using toolchain")
        endif()

        message(">> CMAKE_GENERATOR_PLATFORM: ${CMAKE_GENERATOR_PLATFORM}")
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

        message(">> CMAKE_POSITION_INDEPENDENT_CODE: ${CMAKE_POSITION_INDEPENDENT_CODE}")

        message(">> CMAKE_MODULE_PATH: ${CMAKE_MODULE_PATH}")
        message(">> CMAKE_PREFIX_PATH: ${CMAKE_PREFIX_PATH}")

        find_package(hello REQUIRED)
        add_executable(app app.cpp)
        target_link_libraries(app PRIVATE hello::hello)
        target_compile_definitions(app PRIVATE DEFINITIONS_BOTH="${DEFINITIONS_BOTH}")
        target_compile_definitions(app PRIVATE DEFINITIONS_CONFIG=${DEFINITIONS_CONFIG})
        """)

    def setUp(self):
        # This is intended as a classmethod, this way the client will use the `CMakeCache` between
        #   builds and it will be testing that the toolchain initializes all the variables
        #   properly (it doesn't use preexisting data)
        self.client = TestClient(path_with_spaces=False)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.tools import save
            import os
            class Pkg(ConanFile):
                settings = "build_type"
                def package(self):
                    save(os.path.join(self.package_folder, "include/hello.h"),
                         '#define HELLO_MSG "%s"' % self.settings.build_type)
            """)
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . hello/0.1@ -s build_type=Debug")
        self.client.run("create . hello/0.1@ -s build_type=Release")

        # Prepare the actual consumer package
        self.client.save({"conanfile.py": self.conanfile,
                          "CMakeLists.txt": self.cmakelist,
                          "app.cpp": self.app})

    def _run_build(self, settings=None, options=None):
        # Build the profile according to the settings provided
        settings = settings or {}
        settings = " ".join('-s %s="%s"' % (k, v) for k, v in settings.items() if v)
        options = " ".join("-o %s=%s" % (k, v) for k, v in options.items()) if options else ""

        # Run the configure corresponding to this test case
        build_directory = os.path.join(self.client.current_folder, "build").replace("\\", "/")
        with self.client.chdir(build_directory):
            self.client.run("install .. %s %s" % (settings, options))
            self.client.run("build ..")

    @unittest.skipUnless(platform.system() == "Windows", "Only for windows")
    @parameterized.expand([("Debug", "MTd", "15", "14", "x86", "v140"),
                           ("Release", "MD", "15", "17", "x86_64", "")])
    def test_toolchain_win(self, build_type, runtime, version, cppstd, arch, toolset):
        settings = {"compiler": "Visual Studio",
                    "compiler.version": version,
                    "compiler.toolset": toolset,
                    "compiler.runtime": runtime,
                    "compiler.cppstd": cppstd,
                    "arch": arch,
                    "build_type": build_type,
                    }
        self._run_build(settings)

        # FIXME: Hardcoded VS version and partial toolset check
        self.assertIn('CMake command: cmake -G "Visual Studio 15 2017" '
                      '-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', self.client.out)
        if toolset == "v140":
            self.assertIn("Microsoft Visual Studio 14.0", self.client.out)
        else:
            self.assertIn("Microsoft Visual Studio/2017", self.client.out)

        out = str(self.client.out).splitlines()
        runtime = "MT" if "MT" in runtime else "MD"
        generator_platform = "x64" if arch == "x86_64" else "Win32"
        arch = "x64" if arch == "x86_64" else "X86"
        vals = {"CMAKE_GENERATOR_PLATFORM": generator_platform,
                "CMAKE_BUILD_TYPE": "",
                "CMAKE_CXX_FLAGS": "/MP1 /DWIN32 /D_WINDOWS /W3 /GR /EHsc",
                "CMAKE_CXX_FLAGS_DEBUG": "/%sd /Zi /Ob0 /Od /RTC1" % runtime,
                "CMAKE_CXX_FLAGS_RELEASE": "/%s /O2 /Ob2 /DNDEBUG" % runtime,
                "CMAKE_C_FLAGS": "/MP1 /DWIN32 /D_WINDOWS /W3",
                "CMAKE_C_FLAGS_DEBUG": "/%sd /Zi /Ob0 /Od /RTC1" % runtime,
                "CMAKE_C_FLAGS_RELEASE": "/%s /O2 /Ob2 /DNDEBUG" % runtime,
                "CMAKE_SHARED_LINKER_FLAGS": "/machine:%s" % arch,
                "CMAKE_EXE_LINKER_FLAGS": "/machine:%s" % arch,
                "CMAKE_CXX_STANDARD": cppstd,
                "CMAKE_CXX_EXTENSIONS": "OFF"}
        for k, v in vals.items():
            self.assertIn(">> %s: %s" % (k, v), out)

        toolchain = self.client.load("build/conan_toolchain.cmake")
        include = self.client.load("build/conan_project_include.cmake")
        settings["build_type"] = "Release" if build_type == "Debug" else "Debug"
        self._run_build(settings)
        # The generated toolchain files must be identical
        self.assertEqual(toolchain, self.client.load("build/conan_toolchain.cmake"))
        self.assertEqual(include, self.client.load("build/conan_project_include.cmake"))

        command_str = "build\\Debug\\app.exe"
        self.client.run_command(command_str)
        self.assertIn("Hello: Debug", self.client.out)
        self.assertIn("App: Debug!", self.client.out)
        self.assertIn("DEFINITIONS_BOTH: True", self.client.out)
        self.assertIn("DEFINITIONS_CONFIG: Debug", self.client.out)
        command_str = "build\\Release\\app.exe"
        self.client.run_command(command_str)
        self.assertIn("Hello: Release", self.client.out)
        self.assertIn("App: Release!", self.client.out)
        self.assertIn("DEFINITIONS_BOTH: True", self.client.out)
        self.assertIn("DEFINITIONS_CONFIG: Release", self.client.out)

    @unittest.skipUnless(platform.system() == "Linux", "Only for Linux")
    @parameterized.expand([("Debug",  "14", "x86", "libstdc++"),
                           ("Release", "gnu14", "x86_64", "libstdc++11")])
    def test_toolchain_linux(self, build_type, cppstd, arch, libcxx):
        settings = {"compiler": "gcc",
                    "compiler.cppstd": cppstd,
                    "compiler.libcxx": libcxx,
                    "arch": arch,
                    "build_type": build_type}
        self._run_build(settings)

        self.assertIn('CMake command: cmake -G "Unix Makefiles" '
                      '-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', self.client.out)

        out = str(self.client.out).splitlines()
        extensions_str = "ON" if "gnu" in cppstd else "OFF"
        arch_str = "-m32" if arch == "x86" else "-m64"
        vals = {"CMAKE_CXX_STANDARD": "14",
                "CMAKE_CXX_EXTENSIONS": extensions_str,
                "CMAKE_BUILD_TYPE": build_type,
                "CMAKE_CXX_FLAGS": arch_str,
                "CMAKE_CXX_FLAGS_DEBUG": "-g",
                "CMAKE_CXX_FLAGS_RELEASE": "-O3 -DNDEBUG",
                "CMAKE_C_FLAGS": arch_str,
                "CMAKE_C_FLAGS_DEBUG": "-g",
                "CMAKE_C_FLAGS_RELEASE": "-O3 -DNDEBUG",
                "CMAKE_SHARED_LINKER_FLAGS": arch_str,
                "CMAKE_EXE_LINKER_FLAGS": ""
                }
        for k, v in vals.items():
            self.assertIn(">> %s: %s" % (k, v), out)

        self.client.run_command("build/app")
        self.assertIn("Hello: %s" % build_type, self.client.out)
        self.assertIn("App: %s!" % build_type, self.client.out)
        self.assertIn("DEFINITIONS_BOTH: True", self.client.out)
        self.assertIn("DEFINITIONS_CONFIG: %s" % build_type, self.client.out)


@attr("toolchain")
class OptionsTest(unittest.TestCase):
    @unittest.skipUnless(platform.system() == "Windows", "Only for windows")
    def test_error_fpic(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class App(ConanFile):
                settings = "os"
                options = {"fPIC": [True, False]}
                default_options = {"fPIC": False}
                toolchain = "cmake"
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install . ", assert_error=True)
        self.assertIn("ERROR: fPIC option defined for Windows. Remove it.", client.out)
