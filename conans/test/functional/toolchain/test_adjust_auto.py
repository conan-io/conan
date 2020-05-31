# coding=utf-8

import os
import platform
import re
import textwrap
import unittest

from jinja2 import Template
from nose.plugins.attrib import attr
from parameterized.parameterized import parameterized
from parameterized.parameterized import parameterized_class

from conans.test.functional.toolchain.builds import \
    compile_cache_workflow_with_toolchain, compile_local_workflow, compile_cmake_workflow
from conans.test.utils.tools import TurboTestClient


_running_ci = 'JOB_NAME' in os.environ


@parameterized_class([{"function": compile_cache_workflow_with_toolchain},
                      {"function": compile_local_workflow},
                      {"function": compile_cmake_workflow},
                      ])
@attr("toolchain")
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
            generators = "cmake_find_package"
            options = {"fPIC": [True, False]}
            default_options = {"fPIC": False}

            def toolchain(self):
                return CMakeToolchain(self)

            def build(self):
                # Do not actually build, just configure
                cmake = CMake(self)
                cmake.configure()
    """)
    conanfile = Template(_conanfile).render()

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

        message(">> CMAKE_INSTALL_NAME_DIR: ${CMAKE_INSTALL_NAME_DIR}")
        message(">> CMAKE_SKIP_RPATH: ${CMAKE_SKIP_RPATH}")

        message(">> CMAKE_MODULE_PATH: ${CMAKE_MODULE_PATH}")
        message(">> CMAKE_PREFIX_PATH: ${CMAKE_PREFIX_PATH}")

        message(">> CMAKE_INCLUDE_PATH: ${CMAKE_INCLUDE_PATH}")
        message(">> CMAKE_LIBRARY_PATH: ${CMAKE_LIBRARY_PATH}")

        get_directory_property(_COMPILE_DEFINITONS DIRECTORY ${CMAKE_SOURCE_DIR} COMPILE_DEFINITIONS)
        message(">> COMPILE_DEFINITONS: ${_COMPILE_DEFINITONS}")
    """)

    @classmethod
    def setUpClass(cls):
        # This is intended as a classmethod, this way the client will use the `CMakeCache` between
        #   builds and it will be testing that the toolchain initializes all the variables
        #   properly (it doesn't use preexisting data)
        cls.t = TurboTestClient(path_with_spaces=False)

        # Prepare the actual consumer package
        cls.t.save({"conanfile.py": cls.conanfile,
                    "CMakeLists.txt": cls.cmakelist})

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
        profile_path = os.path.join(self.t.current_folder, "profile").replace("\\", "/")

        # Run the configure corresponding to this test case
        configure_out, cmake_cache, build_directory, package_directory = self.function(client=self.t, profile=profile_path)
        build_directory = build_directory.replace("\\", "/")
        if package_directory:
            package_directory = package_directory.replace("\\", "/")

        # Prepare the outputs for the test cases
        configure_out = [re.sub(r"\s\s+", " ", line) for line in str(configure_out).splitlines()]  # FIXME: There are some extra spaces between flags
        cmake_cache_items = {}
        for line in cmake_cache.splitlines():
            if not line.strip() or line.startswith("//") or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            cmake_cache_items[key] = value
        cmake_cache_keys = [item.split(":")[0] for item in cmake_cache_items.keys()]
        return configure_out, cmake_cache_items, cmake_cache_keys, build_directory, package_directory

    @parameterized.expand([("Debug",), ("Release",)])
    @unittest.skipIf(platform.system() == "Windows", "Windows uses VS, CMAKE_BUILD_TYPE is not used")
    def test_build_type(self, build_type):
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"build_type":
                                                                                  build_type})

        self.assertIn(">> CMAKE_BUILD_TYPE: {}".format(build_type), configure_out)

        self.assertEqual(build_type, cmake_cache["CMAKE_BUILD_TYPE:STRING"])

    @parameterized.expand([("libc++",), ])  # ("libstdc++",), is deprecated
    @unittest.skipIf(platform.system() != "Darwin", "libcxx for Darwin")
    def test_libcxx_macos(self, libcxx):
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"compiler.libcxx":
                                                                                  libcxx})

        self.assertIn("-- Conan: C++ stdlib: {}".format(libcxx), configure_out)
        self.assertIn(">> CMAKE_CXX_FLAGS: -m64 -stdlib={}".format(libcxx), configure_out)
        self.assertNotIn("CONAN_LIBCXX", cmake_cache_keys)

    @parameterized.expand([("libstdc++",), ("libstdc++11", ), ])
    @unittest.skipIf(platform.system() != "Linux", "libcxx for Linux")
    def test_libcxx_linux(self, libcxx):
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"compiler.libcxx":
                                                                                  libcxx})

        self.assertIn("-- Conan: C++ stdlib: {}".format(libcxx), configure_out)
        cxx11_abi_str = "1" if libcxx == "libstdc++11" else "0"
        self.assertIn(">> COMPILE_DEFINITONS: _GLIBCXX_USE_CXX11_ABI={}".format(cxx11_abi_str),
                      configure_out)

        self.assertNotIn("CONAN_LIBCXX", cmake_cache_keys)

    @unittest.skipIf(platform.system() != "Darwin", "Only MacOS")
    def test_ccxx_flags_macos(self):
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure()

        self.assertIn(">> CMAKE_CXX_FLAGS: -m64 -stdlib=libc++", configure_out)
        self.assertIn(">> CMAKE_C_FLAGS: -m64", configure_out)
        self.assertIn(">> CMAKE_CXX_FLAGS_DEBUG: -g", configure_out)
        self.assertIn(">> CMAKE_CXX_FLAGS_RELEASE: -O3 -DNDEBUG", configure_out)
        self.assertIn(">> CMAKE_C_FLAGS_DEBUG: -g", configure_out)
        self.assertIn(">> CMAKE_C_FLAGS_RELEASE: -O3 -DNDEBUG", configure_out)

        self.assertIn(">> CMAKE_SHARED_LINKER_FLAGS: -m64", configure_out)
        self.assertIn(">> CMAKE_EXE_LINKER_FLAGS: ", configure_out)

        self.assertEqual("-m64 -stdlib=libc++", cmake_cache["CMAKE_CXX_FLAGS:STRING"])
        self.assertEqual("-m64", cmake_cache["CMAKE_C_FLAGS:STRING"])
        self.assertEqual("-m64", cmake_cache["CMAKE_SHARED_LINKER_FLAGS:STRING"])
        self.assertEqual("-g", cmake_cache["CMAKE_CXX_FLAGS_DEBUG:STRING"])
        self.assertEqual("-O3 -DNDEBUG", cmake_cache["CMAKE_CXX_FLAGS_RELEASE:STRING"])
        self.assertEqual("-g", cmake_cache["CMAKE_C_FLAGS_DEBUG:STRING"])
        self.assertEqual("-O3 -DNDEBUG", cmake_cache["CMAKE_C_FLAGS_RELEASE:STRING"])

        self.assertEqual("", cmake_cache["CMAKE_EXE_LINKER_FLAGS:STRING"])

    @unittest.skipIf(platform.system() != "Windows", "Not in Windows")
    def test_ccxx_flags_win(self):
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure()

        mp1_prefix = "/MP1 "
        mdd_flag = "MDd"
        self.assertIn(">> CMAKE_CXX_FLAGS: {}/DWIN32 /D_WINDOWS /W3 /GR /EHsc".format(mp1_prefix), configure_out)
        self.assertIn(">> CMAKE_CXX_FLAGS_DEBUG: /{} /Zi /Ob0 /Od /RTC1".format(mdd_flag), configure_out)
        self.assertIn(">> CMAKE_CXX_FLAGS_RELEASE: /MD /O2 /Ob2 /DNDEBUG", configure_out)
        self.assertIn(">> CMAKE_C_FLAGS: {}/DWIN32 /D_WINDOWS /W3".format(mp1_prefix), configure_out)
        self.assertIn(">> CMAKE_C_FLAGS_DEBUG: /{} /Zi /Ob0 /Od /RTC1".format(mdd_flag), configure_out)
        self.assertIn(">> CMAKE_C_FLAGS_RELEASE: /MD /O2 /Ob2 /DNDEBUG", configure_out)

        self.assertIn(">> CMAKE_SHARED_LINKER_FLAGS: /machine:x64", configure_out)
        self.assertIn(">> CMAKE_EXE_LINKER_FLAGS: /machine:x64", configure_out)

        self.assertEqual("/MP1 /DWIN32 /D_WINDOWS /W3 /GR /EHsc", cmake_cache["CMAKE_CXX_FLAGS:STRING"])
        self.assertEqual("/MP1 /DWIN32 /D_WINDOWS /W3", cmake_cache["CMAKE_C_FLAGS:STRING"])

        self.assertEqual("/MDd /Zi /Ob0 /Od /RTC1", cmake_cache["CMAKE_CXX_FLAGS_DEBUG:STRING"])
        self.assertEqual("/MD /O2 /Ob2 /DNDEBUG", cmake_cache["CMAKE_CXX_FLAGS_RELEASE:STRING"])
        self.assertEqual("/MDd /Zi /Ob0 /Od /RTC1", cmake_cache["CMAKE_C_FLAGS_DEBUG:STRING"])
        self.assertEqual("/MD /O2 /Ob2 /DNDEBUG", cmake_cache["CMAKE_C_FLAGS_RELEASE:STRING"])

        self.assertEqual("/machine:x64", cmake_cache["CMAKE_SHARED_LINKER_FLAGS:STRING"])
        self.assertEqual("/machine:x64", cmake_cache["CMAKE_EXE_LINKER_FLAGS:STRING"])

    @unittest.skipIf(platform.system() != "Linux", "Only Linux")
    def test_ccxx_flags_linux(self):
        cache_filepath = os.path.join(self.t.current_folder, "build", "CMakeCache.txt")
        if os.path.exists(cache_filepath):
            os.unlink(cache_filepath)  # FIXME: Ideally this shouldn't be needed (I need it only here)

        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure()

        self.assertIn(">> CMAKE_CXX_FLAGS: -m64", configure_out)
        self.assertIn(">> CMAKE_C_FLAGS: -m64", configure_out)
        self.assertIn(">> CMAKE_CXX_FLAGS_DEBUG: -g", configure_out)
        self.assertIn(">> CMAKE_CXX_FLAGS_RELEASE: -O3 -DNDEBUG", configure_out)
        self.assertIn(">> CMAKE_C_FLAGS_DEBUG: -g", configure_out)
        self.assertIn(">> CMAKE_C_FLAGS_RELEASE: -O3 -DNDEBUG", configure_out)

        self.assertIn(">> CMAKE_SHARED_LINKER_FLAGS: -m64", configure_out)
        self.assertIn(">> CMAKE_EXE_LINKER_FLAGS: ", configure_out)

        self.assertEqual("-m64", cmake_cache["CMAKE_CXX_FLAGS:STRING"])
        self.assertEqual("-m64", cmake_cache["CMAKE_C_FLAGS:STRING"])
        self.assertEqual("-m64", cmake_cache["CMAKE_SHARED_LINKER_FLAGS:STRING"])
        self.assertEqual("-g", cmake_cache["CMAKE_CXX_FLAGS_DEBUG:STRING"])
        self.assertEqual("-O3 -DNDEBUG", cmake_cache["CMAKE_CXX_FLAGS_RELEASE:STRING"])
        self.assertEqual("-g", cmake_cache["CMAKE_C_FLAGS_DEBUG:STRING"])
        self.assertEqual("-O3 -DNDEBUG", cmake_cache["CMAKE_C_FLAGS_RELEASE:STRING"])
        self.assertEqual("", cmake_cache["CMAKE_EXE_LINKER_FLAGS:STRING"])

    @parameterized.expand([("gnu14",), ("14", ), ])
    @unittest.skipIf(platform.system() == "Windows", "Not for windows")
    def test_stdcxx_flags(self, cppstd):
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"compiler.cppstd":
                                                                                  cppstd})

        extensions_str = "ON" if "gnu" in cppstd else "OFF"
        # self.assertIn("compiler.cppstd={}".format(cppstd), configure_out)
        self.assertIn("-- Conan setting CPP STANDARD: 14 WITH EXTENSIONS {}".format(extensions_str),
                      configure_out)
        self.assertIn(">> CMAKE_CXX_STANDARD: 14", configure_out)
        self.assertIn(">> CMAKE_CXX_EXTENSIONS: {}".format(extensions_str), configure_out)

        # FIXME: Cache doesn't match those in CMakeLists
        self.assertNotIn("CMAKE_CXX_STANDARD", cmake_cache_keys)
        self.assertNotIn("CMAKE_CXX_EXTENSIONS", cmake_cache_keys)
        self.assertNotIn("CONAN_STD_CXX_FLAG", cmake_cache_keys)
        self.assertNotIn("CONAN_CMAKE_CXX_EXTENSIONS", cmake_cache_keys)
        self.assertNotIn("CONAN_CMAKE_CXX_STANDARD", cmake_cache_keys)

    @parameterized.expand([("14",), ("17",), ])
    @unittest.skipUnless(platform.system() == "Windows", "Only for windows")
    def test_stdcxx_flags_windows(self, cppstd):
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"compiler.cppstd": cppstd})

        self.assertIn("-- Conan setting CPP STANDARD: {} WITH EXTENSIONS OFF".format(cppstd), configure_out)
        self.assertIn(">> CMAKE_CXX_STANDARD: {}".format(cppstd), configure_out)
        self.assertIn(">> CMAKE_CXX_EXTENSIONS: OFF", configure_out)

        # FIXME: Cache doesn't match those in CMakeLists
        self.assertNotIn("CMAKE_CXX_STANDARD", cmake_cache_keys)
        self.assertNotIn("CMAKE_CXX_EXTENSIONS", cmake_cache_keys)

        self.assertNotIn("CONAN_CMAKE_CXX_EXTENSIONS", cmake_cache_keys)
        self.assertNotIn("CONAN_CMAKE_CXX_STANDARD", cmake_cache_keys)

    @parameterized.expand([("True",), ("False", ), ])
    @unittest.skipIf(platform.system() == "Windows", "fPIC is not used for Windows")
    def test_fPIC(self, fpic):
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure(options_dict={"app:fPIC": fpic})

        fpic_str = "ON" if fpic == "True" else "OFF"
        #self.assertIn("app:fPIC={}".format(fpic), configure_out)
        self.assertIn("-- Conan: Adjusting fPIC flag ({})".format(fpic_str), configure_out)
        self.assertIn(">> CMAKE_POSITION_INDEPENDENT_CODE: {}".format(fpic_str), configure_out)

        self.assertNotIn("CONAN_CMAKE_POSITION_INDEPENDENT_CODE", cmake_cache_keys)
        self.assertNotIn("CMAKE_POSITION_INDEPENDENT_CODE", cmake_cache_keys)

    @unittest.skipIf(platform.system() != "Darwin", "rpath is only handled for Darwin")
    def test_rpath(self):
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure()

        self.assertIn(">> CMAKE_INSTALL_NAME_DIR: ", configure_out)
        self.assertIn(">> CMAKE_SKIP_RPATH: 1", configure_out)
        self.assertEqual("1", cmake_cache["CMAKE_SKIP_RPATH:BOOL"])

    @parameterized.expand([("Debug", "MTd",), ("Debug", "MDd"), ("Release", "MT"), ("Release", "MD")])
    @unittest.skipUnless(platform.system() == "Windows", "Only windows")
    def test_vs_runtime(self, build_type, runtime):
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"compiler.runtime": runtime,
                                                                                  "build_type": build_type})

        mp1_prefix = "/MP1 "
        runtime_debug = runtime + "d" if build_type == "Release" else runtime  # FIXME: no-toolchain uses the same
        runtime_release = runtime[:2] if build_type == "Debug" else runtime

        self.assertIn(">> CMAKE_SHARED_LINKER_FLAGS: /machine:x64", configure_out)
        self.assertIn(">> CMAKE_EXE_LINKER_FLAGS: /machine:x64", configure_out)

        self.assertIn(">> CMAKE_CXX_FLAGS: {}/DWIN32 /D_WINDOWS /W3 /GR /EHsc".format(mp1_prefix), configure_out)
        self.assertIn(">> CMAKE_CXX_FLAGS_DEBUG: /{} /Zi /Ob0 /Od /RTC1".format(runtime_debug), configure_out)  # FIXME: Same runtime for debug and release!
        self.assertIn(">> CMAKE_CXX_FLAGS_RELEASE: /{} /O2 /Ob2 /DNDEBUG".format(runtime_release), configure_out)
        self.assertIn(">> CMAKE_C_FLAGS: {}/DWIN32 /D_WINDOWS /W3".format(mp1_prefix), configure_out)
        self.assertIn(">> CMAKE_C_FLAGS_DEBUG: /{} /Zi /Ob0 /Od /RTC1".format(runtime_debug), configure_out)  # FIXME: Same runtime for debug and release
        self.assertIn(">> CMAKE_C_FLAGS_RELEASE: /{} /O2 /Ob2 /DNDEBUG".format(runtime_release), configure_out)

        self.assertEqual("/MP1 /DWIN32 /D_WINDOWS /W3 /GR /EHsc", cmake_cache["CMAKE_CXX_FLAGS:STRING"])
        self.assertEqual("/MP1 /DWIN32 /D_WINDOWS /W3", cmake_cache["CMAKE_C_FLAGS:STRING"])

        self.assertEqual("/MDd /Zi /Ob0 /Od /RTC1".format(runtime), cmake_cache["CMAKE_CXX_FLAGS_DEBUG:STRING"])
        self.assertEqual("/MD /O2 /Ob2 /DNDEBUG".format(runtime), cmake_cache["CMAKE_CXX_FLAGS_RELEASE:STRING"])
        self.assertEqual("/MDd /Zi /Ob0 /Od /RTC1".format(runtime), cmake_cache["CMAKE_C_FLAGS_DEBUG:STRING"])
        self.assertEqual("/MD /O2 /Ob2 /DNDEBUG".format(runtime), cmake_cache["CMAKE_C_FLAGS_RELEASE:STRING"])

        self.assertEqual("/machine:x64", cmake_cache["CMAKE_SHARED_LINKER_FLAGS:STRING"])
        self.assertEqual("/machine:x64", cmake_cache["CMAKE_EXE_LINKER_FLAGS:STRING"])

        self.assertNotIn("CONAN_LINK_RUNTIME", cmake_cache_keys)

    @parameterized.expand([("15", "x86_64",), ("15", "x86",), ("16", "x86_64"), ("16", "x86")])
    @unittest.skipUnless(platform.system() == "Windows", "Only windows")
    def test_arch_win(self, compiler_version, arch):
        if _running_ci and compiler_version == "16":
            self.skipTest("Visual Studio 16 is not available in the CI")

        cache_filepath = os.path.join(self.t.current_folder, "build", "CMakeCache.txt")
        if os.path.exists(cache_filepath):
            os.unlink(cache_filepath)  # FIXME: Ideally this shouldn't be needed (I need it only here)
        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"arch": arch,
                                                                                  "compiler.version": compiler_version})

        arch_str = "x64" if arch == "x86_64" else "X86"
        self.assertIn(">> CMAKE_SHARED_LINKER_FLAGS: /machine:{}".format(arch_str), configure_out)
        self.assertIn(">> CMAKE_EXE_LINKER_FLAGS: /machine:{}".format(arch_str), configure_out)
        generator_str = "x64" if arch == "x86_64" else "Win32"
        self.assertIn(">> CMAKE_GENERATOR_PLATFORM: {}".format(generator_str), configure_out)

        self.assertEqual("/machine:{}".format(arch_str), cmake_cache["CMAKE_SHARED_LINKER_FLAGS:STRING"])
        self.assertEqual("/machine:{}".format(arch_str), cmake_cache["CMAKE_EXE_LINKER_FLAGS:STRING"])

        self.assertEqual(generator_str, cmake_cache["CMAKE_GENERATOR_PLATFORM:STRING"])

    @parameterized.expand([("x86_64",), ("x86",), ])
    @unittest.skipUnless(platform.system() == "Linux", "Only linux")
    def test_arch_linux(self, arch):
        cache_filepath = os.path.join(self.t.current_folder, "build", "CMakeCache.txt")
        if os.path.exists(cache_filepath):
            os.unlink(cache_filepath)  # FIXME: Ideally this shouldn't be needed (I need it only here)

        configure_out, cmake_cache, cmake_cache_keys, _, _ = self._run_configure({"arch": arch})

        arch_str = "m32" if arch == "x86" else "m64"
        self.assertIn(">> CMAKE_CXX_FLAGS: -{}".format(arch_str), configure_out)
        self.assertIn(">> CMAKE_C_FLAGS: -{}".format(arch_str), configure_out)

        self.assertIn(">> CMAKE_SHARED_LINKER_FLAGS: -{}".format(arch_str), configure_out)
        self.assertIn(">> CMAKE_EXE_LINKER_FLAGS: ", configure_out)

        self.assertEqual("-{}".format(arch_str), cmake_cache["CMAKE_CXX_FLAGS:STRING"])
        self.assertEqual("-{}".format(arch_str), cmake_cache["CMAKE_C_FLAGS:STRING"])
        self.assertEqual("-{}".format(arch_str), cmake_cache["CMAKE_SHARED_LINKER_FLAGS:STRING"])

        self.assertEqual("", cmake_cache["CMAKE_EXE_LINKER_FLAGS:STRING"])
