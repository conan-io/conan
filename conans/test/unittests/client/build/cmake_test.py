import os
import platform
import shutil
import stat
import sys
import unittest

import mock
import six
from parameterized.parameterized import parameterized
import pytest

from conans.client import tools
from conans.client.build.cmake import CMake
from conans.client.build.cmake_flags import cmake_in_local_cache_var_name
from conans.client.conf import get_default_settings_yml
from conans.client.tools import cross_building
from conans.client.tools.oss import cpu_count
from conans.errors import ConanException
from conans.model.build_info import CppInfo, DepsCppInfo
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.test.utils.mocks import MockSettings, ConanFileMock
from conans.test.utils.test_files import temp_folder
from conans.util.files import load, save
from conans.model.conf import ConfDefinition


def _format_path_as_cmake(pathstr):
    if platform.system() == "Windows":
        drive, path = os.path.splitdrive(pathstr)
        return drive.upper() + path.replace(os.path.sep, "/")
    return pathstr


class CMakeTest(unittest.TestCase):

    def setUp(self):
        self.tempdir = temp_folder(path_with_spaces=False)
        self.tempdir2 = temp_folder(path_with_spaces=False)

    def tearDown(self):
        shutil.rmtree(self.tempdir)
        shutil.rmtree(self.tempdir2)

    def test_config_patch(self):

        conanfile = ConanFileMock()
        conanfile.name = "MyPkg"
        conanfile.settings = Settings()
        conanfile.folders.set_base_source(os.path.join(self.tempdir, "src"))
        conanfile.folders.set_base_build(os.path.join(self.tempdir, "build"))
        conanfile.folders.set_base_package(os.path.join(self.tempdir, "pkg"))
        conanfile.deps_cpp_info = DepsCppInfo()

        msg = "FOLDER: " + _format_path_as_cmake(conanfile.package_folder)
        for folder in (conanfile.build_folder, conanfile.package_folder):
            save(os.path.join(folder, "file1.cmake"), "Nothing")
            save(os.path.join(folder, "file2"), msg)
            save(os.path.join(folder, "file3.txt"), msg)
            save(os.path.join(folder, "file3.cmake"), msg)
            save(os.path.join(folder, "sub", "file3.cmake"), msg)

        cmake = CMake(conanfile, generator="Unix Makefiles")
        cmake.patch_config_paths()
        for folder in (conanfile.build_folder, conanfile.package_folder):
            self.assertEqual("Nothing", load(os.path.join(folder, "file1.cmake")))
            self.assertEqual(msg, load(os.path.join(folder, "file2")))
            self.assertEqual(msg, load(os.path.join(folder, "file3.txt")))
            self.assertEqual("FOLDER: ${CONAN_MYPKG_ROOT}",
                             load(os.path.join(folder, "file3.cmake")))
            self.assertEqual("FOLDER: ${CONAN_MYPKG_ROOT}",
                             load(os.path.join(folder, "sub", "file3.cmake")))

    def test_config_patch_deps(self):
        conanfile = ConanFileMock()
        conanfile.name = "MyPkg"
        conanfile.settings = Settings()
        conanfile.folders.set_base_source(os.path.join(self.tempdir, "src"))
        conanfile.folders.set_base_build(os.path.join(self.tempdir, "build"))
        conanfile.folders.set_base_package(os.path.join(self.tempdir, "pkg"))
        conanfile.deps_cpp_info = DepsCppInfo()

        ref = ConanFileReference.loads("MyPkg1/0.1@user/channel")
        cpp_info = CppInfo(ref.name, self.tempdir2)
        conanfile.deps_cpp_info.add(ref.name, cpp_info)
        self.tempdir = temp_folder(path_with_spaces=False)

        self.assertEqual(list(conanfile.deps_cpp_info.deps), ['MyPkg1'])
        self.assertEqual(conanfile.deps_cpp_info['MyPkg1'].rootpath,
                         self.tempdir2)

        msg = "FOLDER: " + _format_path_as_cmake(self.tempdir2)
        for folder in (conanfile.build_folder, conanfile.package_folder):
            save(os.path.join(folder, "file1.cmake"), "Nothing")
            save(os.path.join(folder, "file2"), msg)
            save(os.path.join(folder, "file3.txt"), msg)
            save(os.path.join(folder, "file3.cmake"), msg)
            save(os.path.join(folder, "sub", "file3.cmake"), msg)

        cmake = CMake(conanfile, generator="Unix Makefiles")
        cmake.patch_config_paths()
        for folder in (conanfile.build_folder, conanfile.package_folder):
            self.assertEqual("Nothing", load(os.path.join(folder, "file1.cmake")))
            self.assertEqual(msg, load(os.path.join(folder, "file2")))
            self.assertEqual(msg, load(os.path.join(folder, "file3.txt")))
            self.assertEqual("FOLDER: ${CONAN_MYPKG1_ROOT}",
                             load(os.path.join(folder, "file3.cmake")))
            self.assertEqual("FOLDER: ${CONAN_MYPKG1_ROOT}",
                             load(os.path.join(folder, "sub", "file3.cmake")))

    def test_partial_build(self):
        conanfile = ConanFileMock()
        conanfile.settings = Settings()
        conanfile.should_configure = False
        conanfile.should_build = False
        conanfile.should_install = False
        conanfile.should_test = False
        cmake = CMake(conanfile, generator="Unix Makefiles")
        cmake.configure()
        self.assertIsNone(conanfile.command)
        cmake.build()
        self.assertIsNone(conanfile.command)
        cmake.install()
        self.assertIsNone(conanfile.command)
        conanfile.name = None
        cmake.patch_config_paths()
        cmake.test()
        self.assertIsNone(conanfile.command)

    def test_should_flags(self):
        conanfile = ConanFileMock()
        conanfile.settings = Settings()
        conanfile.should_configure = False
        conanfile.should_build = True
        conanfile.should_install = False
        conanfile.should_test = True
        conanfile.folders.set_base_package(temp_folder())
        cmake = CMake(conanfile, generator="Unix Makefiles")
        cmake.configure()
        self.assertIsNone(conanfile.command)
        cmake.build()
        self.assertIn("cmake --build %s" %
                      CMakeTest.scape(". -- -j%i" % cpu_count(output=conanfile.output)),
                      conanfile.command)
        cmake.install()
        self.assertNotIn("cmake --build %s" %
                         CMakeTest.scape(". --target install -- -j%i" %
                                         cpu_count(output=conanfile.output)), conanfile.command)
        cmake.test()
        self.assertIn("cmake --build %s" %
                      CMakeTest.scape(". --target test -- -j%i" %
                                      cpu_count(output=conanfile.output)),
                      conanfile.command)
        conanfile.should_build = False
        cmake.configure()
        self.assertNotIn("cd . && cmake", conanfile.command)
        cmake.build()
        self.assertNotIn("cmake --build %s" %
                         CMakeTest.scape(". -- -j%i" % cpu_count(output=conanfile.output)),
                         conanfile.command)
        cmake.install()
        self.assertNotIn("cmake --build %s" %
                         CMakeTest.scape(". --target install -- -j%i" %
                                         cpu_count(output=conanfile.output)), conanfile.command)
        cmake.test()
        self.assertIn("cmake --build %s" %
                      CMakeTest.scape(". --target test -- -j%i" %
                                      cpu_count(output=conanfile.output)),
                      conanfile.command)
        conanfile.should_install = True
        conanfile.should_test = False
        cmake.configure()
        self.assertNotIn("cd . && cmake", conanfile.command)
        cmake.build()
        self.assertNotIn("cmake --build %s" %
                         CMakeTest.scape(". -- -j%i" % cpu_count(output=conanfile.output)),
                         conanfile.command)
        cmake.install()
        self.assertIn("cmake --build %s" %
                      CMakeTest.scape(". --target install -- -j%i" %
                                      cpu_count(output=conanfile.output)), conanfile.command)
        cmake.test()
        self.assertNotIn("cmake --build %s" %
                         CMakeTest.scape(". --target test -- -j%i" %
                                         cpu_count(output=conanfile.output)), conanfile.command)

    def test_conan_run_tests(self):
        conanfile = ConanFileMock()
        conanfile.settings = Settings()
        conanfile.should_test = True
        cmake = CMake(conanfile, generator="Unix Makefiles")
        with tools.environment_append({"CONAN_RUN_TESTS": "0"}):
            cmake.test()
            self.assertIsNone(conanfile.command)

    def test_cmake_generator(self):
        conanfile = ConanFileMock()
        conanfile.settings = Settings()
        with tools.environment_append({"CONAN_CMAKE_GENERATOR": "My CMake Generator"}):
            cmake = CMake(conanfile)
            self.assertIn('-G "My CMake Generator"', cmake.command_line)

    def test_cmake_generator_intel(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "intel"
        settings.compiler.version = "19"
        settings.compiler.base = "Visual Studio"
        settings.compiler.base.version = "15"
        settings.arch = "x86_64"

        conanfile = ConanFileMock()
        conanfile.settings = settings

        cmake = CMake(conanfile)
        self.assertIn('-G "Visual Studio 15 2017 Win64"', cmake.command_line)
        self.assertIn('-T "Intel C++ Compiler 19.0', cmake.command_line)

    def test_cmake_custom_generator_intel(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "intel"
        settings.compiler.version = "19"
        settings.compiler.base = "Visual Studio"
        settings.compiler.base.version = "15"
        settings.arch = "x86_64"

        conanfile = ConanFileMock()
        conanfile.settings = settings

        with tools.environment_append({"CONAN_CMAKE_GENERATOR": "My CMake Generator"}):
            cmake = CMake(conanfile)
            self.assertIn('-G "My CMake Generator"', cmake.command_line)
            self.assertNotIn('-G "Visual Studio 15 2017" -A "x64"', cmake.command_line)
            self.assertNotIn('-T "Intel C++ Compiler 19.0', cmake.command_line)

    @parameterized.expand([("SunOS", "sparcv9", "sparc"),
                           ("AIX", "ppc64", "ppc32"),
                           ("SunOS", "x86_64", "x86")])
    def test_cmake_not_cross_compile(self, os_build, arch_build, arch):
        # https://github.com/conan-io/conan/issues/8052
        settings = Settings.loads(get_default_settings_yml())
        settings.os = os_build
        settings.os_build = os_build
        settings.compiler = "gcc"
        settings.compiler.version = "9.2"
        settings.compiler.libcxx = "libstdc++"
        settings.arch = arch
        settings.arch_build = arch_build

        conanfile = ConanFileMock()
        conanfile.settings = settings

        cmake = CMake(conanfile)
        self.assertNotIn('CMAKE_SYSTEM_NAME', cmake.command_line)
        self.assertIn('-G "Unix Makefiles"', cmake.command_line)

    def test_cmake_generator_platform(self):
        conanfile = ConanFileMock()
        conanfile.settings = Settings()

        with tools.environment_append({"CONAN_CMAKE_GENERATOR": "Green Hills MULTI",
                                       "CONAN_CMAKE_GENERATOR_PLATFORM": "My CMake Platform"}):
            cmake = CMake(conanfile)
            self.assertIn('-G "Green Hills MULTI" -A "My CMake Platform"', cmake.command_line)

    def test_cmake_generator_platform_override(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"

        conanfile = ConanFileMock()
        conanfile.settings = settings

        with tools.environment_append({"CONAN_CMAKE_GENERATOR_PLATFORM": "Win64"}):
            cmake = CMake(conanfile)
            self.assertIn('-G "Visual Studio 15 2017" -A "Win64"', cmake.command_line)

    def test_cmake_generator_argument(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.compiler.toolset = "v141"
        settings.arch = "x86_64"

        conanfile = ConanFileMock()
        conanfile.settings = settings

        cmake = CMake(conanfile, generator="Visual Studio 16 2019")
        self.assertIn('-G "Visual Studio 16 2019" -A "x64"', cmake.command_line)
        cmake.build()
        self.assertIn("/verbosity:minimal", conanfile.command)
        cmake = CMake(conanfile, generator="Visual Studio 9 2008")
        self.assertIn('-G "Visual Studio 9 2008 Win64"', cmake.command_line)
        cmake.build()
        self.assertNotIn("verbosity", conanfile.command)

    def test_cmake_generator_platform_gcc(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Linux"
        settings.os_build = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "8"
        settings.compiler.libcxx = "libstdc++"
        settings.arch = "x86"

        conanfile = ConanFileMock()
        conanfile.settings = settings

        cmake = CMake(conanfile)
        self.assertIn('-G "Unix Makefiles"', cmake.command_line)
        self.assertNotIn('-A', cmake.command_line)

    @parameterized.expand([('x86', 'Visual Studio 15 2017'),
                           ('x86_64', 'Visual Studio 15 2017 Win64'),
                           ('armv7', 'Visual Studio 15 2017 ARM')])
    def test_cmake_generator_platform_vs2017(self, arch, generator):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = arch

        conanfile = ConanFileMock()
        conanfile.settings = settings

        cmake = CMake(conanfile)
        self.assertIn('-G "%s"' % generator, cmake.command_line)
        self.assertNotIn('-A', cmake.command_line)

    @parameterized.expand([('x86', 'Win32'),
                           ('x86_64', 'x64'),
                           ('armv7', 'ARM'),
                           ('armv8', 'ARM64')])
    def test_cmake_generator_platform_vs2019(self, arch, pf):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "16"
        settings.arch = arch

        conanfile = ConanFileMock()
        conanfile.settings = settings

        cmake = CMake(conanfile)
        self.assertIn('-G "Visual Studio 16 2019" -A "%s"' % pf, cmake.command_line)

    def test_cmake_generator_platform_vs2019_with_ninja(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "16"
        settings.arch = "x86_64"

        conanfile = ConanFileMock()
        conanfile.settings = settings

        cmake = CMake(conanfile, generator="Ninja")
        self.assertIn('-G "Ninja"', cmake.command_line)
        self.assertNotIn("-A", cmake.command_line)

    @parameterized.expand([('arm',),
                           ('ppc',),
                           ('86',)])
    def test_cmake_generator_platform_other(self, arch):
        conanfile = ConanFileMock()
        conanfile.settings = Settings()

        with tools.environment_append({"CONAN_CMAKE_GENERATOR": "Green Hills MULTI",
                                       "CONAN_CMAKE_GENERATOR_PLATFORM": arch}):
            cmake = CMake(conanfile)
            self.assertIn('-G "Green Hills MULTI" -A "%s"' % arch, cmake.command_line)

    @parameterized.expand([('Ninja',),
                           ('NMake Makefiles',),
                           ('NMake Makefiles JOM',)
                           ])
    def test_generator_platform_with_unsupported_generator(self, generator):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.compiler.toolset = "v140"

        conanfile = ConanFileMock()
        conanfile.settings = settings

        with self.assertRaises(ConanException):
            cmake = CMake(conanfile, generator=generator, generator_platform="x64")
            _ = cmake.command_line

    def test_cmake_fpic(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "6.3"
        settings.arch = "x86"

        def assert_fpic(the_settings, input_shared, input_fpic, expected_option):
            options = []
            values = {}
            if input_shared is not None:
                options.append('"shared": [True, False]')
                values["shared"] = input_shared
            if input_fpic is not None:
                options.append('"fPIC": [True, False]')
                values["fPIC"] = input_fpic

            conanfile = ConanFileMock(options='{%s}' % ", ".join(options),
                                      options_values=values)
            conanfile.settings = the_settings
            cmake = CMake(conanfile)
            cmake.configure()
            if expected_option is not None:
                self.assertEqual(cmake.definitions["CONAN_CMAKE_POSITION_INDEPENDENT_CODE"],
                                 expected_option)
            else:
                self.assertNotIn("CONAN_CMAKE_POSITION_INDEPENDENT_CODE", cmake.definitions)

        # Test shared=False and fpic=False
        assert_fpic(settings, input_shared=False, input_fpic=False, expected_option="OFF")

        # Test shared=True and fpic=False
        assert_fpic(settings, input_shared=True, input_fpic=False, expected_option="ON")

        # Test shared=True and fpic=True
        assert_fpic(settings, input_shared=True, input_fpic=True, expected_option="ON")

        # Test shared not defined and fpic=True
        assert_fpic(settings, input_shared=None, input_fpic=True, expected_option="ON")

        # Test shared not defined and fpic not defined
        assert_fpic(settings, input_shared=None, input_fpic=None, expected_option=None)

        # Test shared True and fpic not defined
        assert_fpic(settings, input_shared=True, input_fpic=None, expected_option=None)

        # Test nothing in Windows
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86_64"

        assert_fpic(settings, input_shared=True, input_fpic=True, expected_option=None)

    def test_cmake_make_program(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "6.3"
        settings.arch = "x86"
        settings.build_type = "Release"
        conanfile = ConanFileMock()
        conanfile.settings = settings
        conanfile.folders.set_base_source(os.path.join(self.tempdir, "my_cache_source_folder"))
        conanfile.folders.set_base_build(os.path.join(self.tempdir, "my_cache_build_folder"))

        # Existing make
        make_path = os.path.join(self.tempdir, "make")
        save(make_path, "")
        st = os.stat(make_path)
        os.chmod(make_path, st.st_mode | stat.S_IEXEC)
        with tools.environment_append({"CONAN_MAKE_PROGRAM": make_path}):
            cmake = CMake(conanfile)
            self.assertEqual(cmake.definitions["CMAKE_MAKE_PROGRAM"], make_path)

        # Not existing make
        with tools.environment_append({"CONAN_MAKE_PROGRAM": "fake_path/make"}):
            cmake = CMake(conanfile)
            self.assertNotIn("CMAKE_MAKE_PROGRAM", cmake.definitions)
            self.assertIn("The specified make program 'fake_path/make' cannot be found",
                          conanfile.output)

    def test_folders(self):
        def quote_var(var):
            return "'%s'" % var if platform.system() != "Windows" else var

        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "6.3"
        settings.arch = "x86"
        settings.build_type = "Release"

        conanfile = ConanFileMock()
        conanfile.settings = settings
        conanfile.folders.set_base_source(os.path.join(self.tempdir, "my_cache_source_folder"))
        conanfile.folders.set_base_build(os.path.join(self.tempdir, "my_cache_build_folder"))
        with tools.chdir(self.tempdir):
            linux_stuff = ""
            if platform.system() != "Linux":
                linux_stuff = '-DCMAKE_SYSTEM_NAME="Linux" -DCMAKE_SYSROOT="/path/to/sysroot" '
            generator = "MinGW Makefiles" if platform.system() == "Windows" else "Unix Makefiles"

            flags = '{} -DCONAN_COMPILER="gcc" ' \
                    '-DCONAN_COMPILER_VERSION="6.3" ' \
                    '-DCONAN_CXX_FLAGS="-m32" -DCONAN_SHARED_LINKER_FLAGS="-m32" ' \
                    '-DCONAN_C_FLAGS="-m32" -DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" ' \
                    '-DCONAN_EXPORTED="1"'
            flags_in_local_cache = flags.format('-D' + cmake_in_local_cache_var_name + '="ON"')
            flags_no_local_cache = flags.format('-D' + cmake_in_local_cache_var_name + '="OFF"')

            base_cmd = 'cmake -G "{generator}" -DCMAKE_BUILD_TYPE="Release" {linux_stuff}' \
                       '{{flags}} -Wno-dev'
            base_cmd = base_cmd.format(generator=generator, linux_stuff=linux_stuff)
            full_cmd = "cd {build_expected} && {base_cmd} {source_expected}"

            build_expected = quote_var("build")
            source_expected = quote_var("../subdir")

            cmake = CMake(conanfile)
            cmake.configure(source_dir="../subdir", build_dir="build")
            self.assertEqual(conanfile.command,
                             full_cmd.format(build_expected=build_expected,
                                             source_expected=source_expected,
                                             base_cmd=base_cmd.format(flags=flags_no_local_cache)))

            cmake = CMake(conanfile)
            cmake.configure(build_dir="build")
            build_expected = quote_var("build")
            source_expected = quote_var(os.path.join(self.tempdir, "my_cache_source_folder"))
            self.assertEqual(conanfile.command,
                             full_cmd.format(build_expected=build_expected,
                                             source_expected=source_expected,
                                             base_cmd=base_cmd.format(flags=flags_no_local_cache)))

            cmake = CMake(conanfile)
            cmake.configure()
            build_expected = quote_var(os.path.join(self.tempdir, "my_cache_build_folder"))
            source_expected = quote_var(os.path.join(self.tempdir, "my_cache_source_folder"))
            self.assertEqual(conanfile.command,
                             full_cmd.format(build_expected=build_expected,
                                             source_expected=source_expected,
                                             base_cmd=base_cmd.format(flags=flags_no_local_cache)))

            cmake = CMake(conanfile)
            cmake.configure(source_folder="source", build_folder="build")
            build_expected = quote_var(os.path.join(os.path.join(self.tempdir,
                                                                 "my_cache_build_folder", "build")))
            source_expected = quote_var(os.path.join(os.path.join(self.tempdir,
                                                                  "my_cache_source_folder",
                                                                  "source")))
            self.assertEqual(conanfile.command,
                             full_cmd.format(build_expected=build_expected,
                                             source_expected=source_expected,
                                             base_cmd=base_cmd.format(flags=flags_no_local_cache)))

            conanfile.in_local_cache = True
            cmake = CMake(conanfile)
            cmake.configure(source_folder="source", build_folder="build",
                            cache_build_folder="rel_only_cache")
            build_expected = quote_var(os.path.join(self.tempdir, "my_cache_build_folder",
                                                    "rel_only_cache"))
            source_expected = quote_var(os.path.join(self.tempdir, "my_cache_source_folder",
                                                     "source"))
            self.assertEqual(conanfile.command,
                             full_cmd.format(build_expected=build_expected,
                                             source_expected=source_expected,
                                             base_cmd=base_cmd.format(flags=flags_in_local_cache)))

            conanfile.in_local_cache = False
            cmake = CMake(conanfile)
            cmake.configure(source_folder="source", build_folder="build",
                            cache_build_folder="rel_only_cache")
            build_expected = quote_var(os.path.join(self.tempdir, "my_cache_build_folder", "build"))
            source_expected = quote_var(os.path.join(self.tempdir, "my_cache_source_folder",
                                                     "source"))
            self.assertEqual(conanfile.command,
                             full_cmd.format(build_expected=build_expected,
                                             source_expected=source_expected,
                                             base_cmd=base_cmd.format(flags=flags_no_local_cache)))

            conanfile.in_local_cache = True
            cmake = CMake(conanfile)
            cmake.configure(build_dir="build", cache_build_folder="rel_only_cache")
            build_expected = quote_var(os.path.join(self.tempdir, "my_cache_build_folder",
                                                    "rel_only_cache"))
            source_expected = quote_var(os.path.join(self.tempdir, "my_cache_source_folder"))
            self.assertEqual(conanfile.command, full_cmd.format(build_expected=build_expected,
                                                                source_expected=source_expected,
                                                                base_cmd=base_cmd.format(
                                                                        flags=flags_in_local_cache)))

            # Raise mixing
            with six.assertRaisesRegex(self, ConanException, "Use 'build_folder'/'source_folder'"):
                cmake = CMake(conanfile)
                cmake.configure(source_folder="source", build_dir="build")

    def test_build_type_force(self):
        # 1: No multi-config generator
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "6.3"
        settings.arch = "x86"
        settings.build_type = "Release"
        conanfile = ConanFileMock()
        conanfile.settings = settings
        # 2: build_type from settings
        cmake = CMake(conanfile)
        self.assertNotIn('WARN: Forced CMake build type ', conanfile.output)
        self.assertEqual(cmake.build_type, "Release")

        # 2: build_type from attribute
        cmake.build_type = "Debug"
        expected_output = "WARN: Forced CMake build type ('Debug') different from the settings " \
                          "build type ('Release')"
        self.assertIn(expected_output, conanfile.output)
        self.assertEqual(cmake.build_type, "Debug")
        self.assertIn('-DCMAKE_BUILD_TYPE="Debug"', cmake.command_line)

        # 2: build_type from constructor
        cmake = CMake(conanfile, build_type="Debug")
        expected_output = "WARN: Forced CMake build type ('Debug') different from the settings " \
                          "build type ('Release')"
        self.assertIn(expected_output, conanfile.output)
        self.assertEqual(cmake.build_type, "Debug")
        self.assertIn('-DCMAKE_BUILD_TYPE="Debug"', cmake.command_line)

        # 1: Multi-config generator
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.build_type = "Release"
        conanfile = ConanFileMock()
        conanfile.settings = settings
        # 2: build_type from settings
        cmake = CMake(conanfile)
        self.assertNotIn('-DCMAKE_BUILD_TYPE="Release"', cmake.command_line)
        self.assertIn("--config Release", cmake.build_config)

        # 2: build_type from attribute
        cmake.build_type = "Debug"
        self.assertIn(expected_output, conanfile.output)
        self.assertEqual(cmake.build_type, "Debug")
        self.assertNotIn('-DCMAKE_BUILD_TYPE="Debug"', cmake.command_line)
        self.assertIn("--config Debug", cmake.build_config)

        # 2: build_type from constructor
        cmake = CMake(conanfile, build_type="Debug")
        self.assertIn(expected_output, conanfile.output)
        self.assertEqual(cmake.build_type, "Debug")
        self.assertNotIn('-DCMAKE_BUILD_TYPE="Debug"', cmake.command_line)
        self.assertIn("--config Debug", cmake.build_config)

    def test_loads_default(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"
        conanfile = ConanFileMock()
        conanfile.settings = settings

        def check(text, build_config, generator=None, set_cmake_flags=False):
            the_os = str(settings.os)
            os_ver = str(settings.os.version) if settings.get_safe('os.version') else None
            for cmake_system_name in (True, False):
                cross_ver = ("-DCMAKE_SYSTEM_VERSION=\"%s\" " % os_ver) if os_ver else ""
                # FIXME: This test is complicated to maintain and see the logic, lets simplify it
                cross = ""
                skip_x64_x86 = the_os in ['Windows', 'Linux']
                if cmake_system_name and cross_building(conanfile, skip_x64_x86=skip_x64_x86):
                    cross = ("-DCMAKE_SYSTEM_NAME=\"%s\" %s-DCMAKE_SYSROOT=\"/path/to/sysroot\" "
                             % ({"Macos": "Darwin"}.get(the_os, the_os), cross_ver))
                cmake = CMake(conanfile, generator=generator, cmake_system_name=cmake_system_name,
                              set_cmake_flags=set_cmake_flags)
                new_text = text.replace("-DCONAN_IN_LOCAL_CACHE", "%s-DCONAN_IN_LOCAL_CACHE" % cross)
                if "Visual Studio" in text:
                    cores = ('-DCONAN_CXX_FLAGS="/MP{0}" '
                             '-DCONAN_C_FLAGS="/MP{0}" '.format(tools.cpu_count(conanfile.output)))
                    new_text = new_text.replace('-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON"',
                                                '%s-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON"' % cores)
                self.assertEqual(new_text, cmake.command_line)
                self.assertEqual(build_config, cmake.build_config)

        check('-G "Visual Studio 12 2013" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev',
              "")

        check('-G "Custom Generator" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev',
              '', generator="Custom Generator")

        check('-G "Custom Generator" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev',
              '', generator="Custom Generator", set_cmake_flags=True)

        settings.build_type = "Debug"
        check('-G "Visual Studio 12 2013" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev',
              '--config Debug')

        settings.arch = "x86_64"
        check('-G "Visual Studio 12 2013 Win64" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev',
              '--config Debug')

        settings.compiler = "gcc"
        settings.compiler.version = "4.8"
        cmakegen = "MinGW Makefiles" if platform.system() == "Windows" else "Unix Makefiles"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="gcc" -DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" '
              '-Wno-dev' % cmakegen, "")

        settings.os = "Linux"
        settings.arch = "x86"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug" '
              '-DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="gcc" '
              '-DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS="-m32" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m32" -DCONAN_C_FLAGS="-m32" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev' % cmakegen,
              "")

        settings.arch = "armv7"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug" '
              '-DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="gcc" '
              '-DCONAN_COMPILER_VERSION="4.8" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev' % cmakegen,
              "")

        settings.arch = "x86_64"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug" '
              '-DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="gcc" '
              '-DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev' % cmakegen,
              "")

        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug" '
              '-DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="gcc" '
              '-DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" '
              '-DCMAKE_CXX_FLAGS="-m64" -DCMAKE_SHARED_LINKER_FLAGS="-m64" -DCMAKE_C_FLAGS="-m64" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" '
              '-Wno-dev' % cmakegen,
              "", set_cmake_flags=True)

        settings.os = "FreeBSD"
        settings.compiler = "clang"
        settings.compiler.version = "3.8"
        settings.arch = "x86"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug" '
              '-DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="clang" '
              '-DCONAN_COMPILER_VERSION="3.8" -DCONAN_CXX_FLAGS="-m32" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m32" -DCONAN_C_FLAGS="-m32" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev' % cmakegen,
              "")

        settings.arch = "x86_64"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug" '
              '-DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="clang" '
              '-DCONAN_COMPILER_VERSION="3.8" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev' % cmakegen,
              "")

        settings.os = "SunOS"
        settings.compiler = "sun-cc"
        settings.compiler.version = "5.10"
        settings.arch = "x86"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug" '
              '-DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS="-m32" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m32" -DCONAN_C_FLAGS="-m32" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev' % cmakegen,
              "")

        settings.arch = "x86_64"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug" '
              '-DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev' % cmakegen,
              "")

        settings.arch = "sparc"

        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS="-m32" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m32" -DCONAN_C_FLAGS="-m32" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev' % cmakegen,
              "")

        settings.arch = "sparcv9"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev' % cmakegen,
              "")

        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.os = "WindowsStore"
        settings.os.version = "8.1"
        settings.build_type = "Debug"
        check('-G "Visual Studio 12 2013" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev',
              "--config Debug")

        settings.os.version = "10.0"
        check('-G "Visual Studio 12 2013" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev',
              "--config Debug")

        settings.compiler.version = "15"
        settings.arch = "armv8"
        check('-G "Visual Studio 15 2017" -A "ARM64" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="15" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev',
              "--config Debug")

        settings.arch = "x86_64"
        check('-G "Visual Studio 15 2017 Win64" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="15" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev',
              "--config Debug")

        settings.compiler = "Visual Studio"
        settings.compiler.version = "9"
        settings.os = "WindowsCE"
        settings.os.platform = "Your platform name (ARMv4I)"
        settings.os.version = "7.0"
        settings.build_type = "Debug"
        check('-G "Visual Studio 9 2008" '
              '-A "Your platform name (ARMv4I)" '
              '-DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="9" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" -Wno-dev',
              "--config Debug")

    def test_deleted_os(self):
        partial_settings = """
os: [Linux]
arch: [x86_64]
compiler:
    gcc:
        version: ["4.9"]
build_type: [ Release]
"""
        settings = Settings.loads(partial_settings)
        settings.os = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "4.9"
        settings.arch = "x86_64"
        conanfile = ConanFileMock()
        conanfile.settings = settings

        cmake = CMake(conanfile)
        generator = "Unix" if platform.system() != "Windows" else "MinGW"
        cross = ("-DCMAKE_SYSTEM_NAME=\"Linux\" -DCMAKE_SYSROOT=\"/path/to/sysroot\" "
                 if platform.system() != "Linux" else "")
        self.assertEqual('-G "%s Makefiles" %s-DCONAN_IN_LOCAL_CACHE="OFF" '
                         '-DCONAN_COMPILER="gcc" '
                         '-DCONAN_COMPILER_VERSION="4.9" -DCONAN_CXX_FLAGS="-m64" '
                         '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" '
                         '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" '
                         '-Wno-dev' % (generator, cross),
                         cmake.command_line)

    def test_sysroot(self):
        settings = Settings.loads(get_default_settings_yml())
        conanfile = ConanFileMock()
        conanfile.settings = settings
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"
        if platform.system() == "Windows":
            cmake = CMake(conanfile)
            self.assertNotIn("-DCMAKE_SYSROOT=", cmake.flags)

        # Now activate cross build and check sysroot and system processor
        with(tools.environment_append({"CONAN_CMAKE_SYSTEM_NAME": "Android",
                                       "CONAN_CMAKE_SYSTEM_PROCESSOR": "somevalue"})):
            cmake = CMake(conanfile)
            self.assertEqual(cmake.definitions["CMAKE_SYSROOT"], "/path/to/sysroot")
            self.assertEqual(cmake.definitions["CMAKE_SYSTEM_PROCESSOR"], "somevalue")

    def test_sysroot_envvar(self):
        settings = Settings.loads(get_default_settings_yml())
        conanfile = ConanFileMock()
        conanfile.settings = settings
        settings.os = "Linux"
        settings.os_build = "Windows"
        settings.compiler = "gcc"
        settings.compiler.version = "5"
        settings.arch_build = "x86_64"
        settings.arch = "armv7"

        # Now activate cross build and check sysroot and system processor
        with(tools.environment_append({"CONAN_CMAKE_SYSROOT": "/path/to/var/sysroot"})):
            cmake = CMake(conanfile)
            self.assertEqual(cmake.definitions["CMAKE_SYSROOT"], "/path/to/var/sysroot")

    def test_deprecated_behaviour(self):
        """"Remove when deprecate the old settings parameter to CMake and
        conanfile to configure/build/test"""
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        conanfile = ConanFileMock()
        conanfile.settings = settings
        with self.assertRaises(ConanException):
            CMake(settings)

    def test_cores_ancient_visual(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "9"
        settings.compiler.runtime = "MDd"
        settings.arch = "x86"
        settings.build_type = None

        conanfile = ConanFileMock()
        conanfile.settings = settings
        cmake = CMake(conanfile)

        cmake.build()
        self.assertNotIn("/m", conanfile.command)

        settings.compiler.version = "10"
        cmake = CMake(conanfile)

        cmake.build()
        self.assertIn("/m", conanfile.command)

    def test_convenient_functions(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Android"
        settings.os.api_level = 16
        settings.os_build = "Windows"  # Here we are declaring we are cross building
        settings.compiler = "gcc"
        settings.compiler.version = "5.4"
        settings.arch = "armv7"
        settings.build_type = None

        if platform.system() == 'Windows':
            dot_dir = "."
            tempdir = self.tempdir
        else:
            dot_dir = "'.'"
            tempdir = "'" + self.tempdir + "'"

        conanfile = ConanFileMock()
        conanfile.settings = settings
        cmake = CMake(conanfile)

        cross = '-DCMAKE_SYSTEM_NAME="Android"' \
                ' -DCMAKE_SYSTEM_VERSION="{0}"' \
                ' -DCMAKE_SYSROOT="/path/to/sysroot"' \
                ' -DCMAKE_ANDROID_ARCH_ABI="armeabi-v7a"' \
                ' -DANDROID_ABI="armeabi-v7a"' \
                ' -DANDROID_PLATFORM="android-{0}"' \
                ' -DANDROID_TOOLCHAIN="{1}"' \
                ' -DANDROID_STL="none"'.format(settings.os.api_level, settings.compiler)
        target_test = CMakeTest.scape('--target test')

        cmake.configure()

        self.assertEqual('cd {0} && cmake -G "MinGW Makefiles" '
                         '{1} -DCONAN_IN_LOCAL_CACHE="OFF"'
                         ' -DCONAN_COMPILER="{2}" -DCONAN_COMPILER_VERSION="{3}"'
                         ' -DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON"'
                         ' -DCONAN_EXPORTED="1"'
                         ' -Wno-dev {0}'.format(dot_dir, cross, settings.compiler,
                                                settings.compiler.version),
                         conanfile.command)

        cmake.build()
        self.assertEqual('cmake --build %s %s' %
                         (dot_dir, (CMakeTest.scape('-- -j%i' % cpu_count(conanfile.output)))),
                         conanfile.command)

        cmake.test()
        self.assertEqual('cmake --build %s %s %s' %
                         (dot_dir, target_test,
                          (CMakeTest.scape('-- -j%i' % cpu_count(output=conanfile.output)))),
                         conanfile.command)

        settings.build_type = "Debug"
        cmake = CMake(conanfile)
        cmake.build()
        self.assertEqual('cmake --build %s %s' %
                         (dot_dir, (CMakeTest.scape('-- -j%i' %
                                                    cpu_count(output=conanfile.output)))),
                         conanfile.command)

        cmake.test()
        self.assertEqual('cmake --build %s %s %s' %
                         (dot_dir, target_test,
                          (CMakeTest.scape('-- -j%i' % cpu_count(output=conanfile.output)))),
                         conanfile.command)

        cmake.configure(source_dir="/source", build_dir=self.tempdir,
                        args=['--foo "bar"'], defs={"SHARED": True})
        if sys.platform == 'win32':
            escaped_args = r'"--foo \"bar\"" -DSHARED="True" /source'
        else:
            escaped_args = "'--foo \"bar\"' -DSHARED=\"True\" '/source'"

        self.assertEqual('cd {0} && cmake -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE="Debug" '
                         '{1} -DCONAN_IN_LOCAL_CACHE="OFF" '
                         '-DCONAN_COMPILER="{2}" -DCONAN_COMPILER_VERSION="{3}" '
                         '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -DCONAN_EXPORTED="1" '
                         '-Wno-dev {4}'.format(tempdir, cross, settings.compiler,
                                               settings.compiler.version, escaped_args),
                         conanfile.command)

        cmake.build(args=["--bar 'foo'"], target="install")
        if platform.system() == 'Windows':
            escaped_args = '--target install "--bar \'foo\'"'
        else:
            escaped_args = r"'--target' 'install' '--bar '\''foo'\'''"
        self.assertEqual('cmake --build %s %s %s' %
                         (tempdir, escaped_args,
                          (CMakeTest.scape('-- -j%i' % cpu_count(output=conanfile.output)))),
                         conanfile.command)

        cmake.test(args=["--bar 'foo'"])
        if sys.platform == 'win32':
            escaped_args = '%s "--bar \'foo\'"' % target_test
        else:
            escaped_args = r"%s '--bar '\''foo'\'''" % target_test
        self.assertEqual('cmake --build %s %s %s' %
                         (tempdir, escaped_args,
                          (CMakeTest.scape('-- -j%i' % cpu_count(output=conanfile.output)))),
                         conanfile.command)

        settings.build_type = "Release"
        cmake = CMake(conanfile)
        cmake.build()
        self.assertEqual('cmake --build %s %s' %
                         (dot_dir, (CMakeTest.scape('-- -j%i' %
                                                    cpu_count(output=conanfile.output)))),
                         conanfile.command)

        cmake.test()
        self.assertEqual('cmake --build %s %s %s'
                         % (dot_dir, target_test,
                            (CMakeTest.scape('-- -j%i' % cpu_count(output=conanfile.output)))),
                         conanfile.command)

        cmake.build(build_dir=self.tempdir)
        self.assertEqual('cmake --build %s %s'
                         % (tempdir, (CMakeTest.scape('-- -j%i' %
                                                      cpu_count(output=conanfile.output)))),
                         conanfile.command)

        cmake.test(build_dir=self.tempdir)
        self.assertEqual('cmake --build %s %s %s' %
                         (tempdir, target_test,
                          (CMakeTest.scape('-- -j%i' % cpu_count(output=conanfile.output)))),
                         conanfile.command)

        settings.compiler = "gcc"
        settings.compiler.version = "5.4"
        cmake = CMake(conanfile)
        cmake.build()
        self.assertEqual('cmake --build %s' %
                         (CMakeTest.scape('. -- -j%i' % cpu_count(output=conanfile.output))),
                         conanfile.command)

        cmake.test()
        self.assertEqual('cmake --build %s' %
                         (CMakeTest.scape('. --target test -- -j%i' %
                                          cpu_count(output=conanfile.output))),
                         conanfile.command)

        cmake.build(args=['foo', '--', 'bar'])
        self.assertEqual('cmake --build %s' %
                         (CMakeTest.scape('. foo -- bar -j%i' %
                                          cpu_count(output=conanfile.output))),
                         conanfile.command)

        cmake.test(args=['foo', '--', 'bar'])
        self.assertEqual('cmake --build %s' %
                         (CMakeTest.scape('. --target test foo -- bar -j%i' %
                                          cpu_count(output=conanfile.output))),
                         conanfile.command)

        cmake = CMake(conanfile, parallel=False)
        cmake.build()
        self.assertEqual('cmake --build %s' % CMakeTest.scape('.'), conanfile.command)

        cmake.test()
        self.assertEqual('cmake --build %s' % CMakeTest.scape('. --target test'),
                         conanfile.command)

    def test_run_tests(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "14"
        settings.compiler.runtime = "MDd"
        settings.arch = "x86"
        settings.build_type = None

        conanfile = ConanFileMock()
        conanfile.settings = settings
        cmake = CMake(conanfile)
        cmake.test()
        self.assertIn('cmake --build '
                      '%s' % CMakeTest.scape('. --target RUN_TESTS -- /m:%i' %
                                             cpu_count(output=conanfile.output)),
                      conanfile.command)

        cmake.generator = "Ninja Makefiles"
        cmake.test()
        self.assertEqual('cmake --build '
                         '%s' % CMakeTest.scape('. --target test -- -j%i' %
                                                cpu_count(output=conanfile.output)),
                         conanfile.command)

        cmake.generator = "Ninja"
        cmake.test()
        self.assertEqual('cmake --build '
                         '%s' % CMakeTest.scape('. --target test -- -j%i' %
                                                cpu_count(output=conanfile.output)),
                         conanfile.command)

        cmake.generator = "NMake Makefiles"
        cmake.test()
        self.assertEqual('cmake --build '
                         '%s' % CMakeTest.scape('. --target test'),
                         conanfile.command)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Only for Windows")
    def test_clean_sh_path(self):
        os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + self.tempdir
        save(os.path.join(self.tempdir, "sh.exe"), "Fake sh")
        conanfile = ConanFileMock()
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"
        conanfile.settings = settings

        cmake = CMake(conanfile)
        cmake.configure()
        self.assertIn(self.tempdir, conanfile.path)

        cmake.generator = "MinGW Makefiles"
        cmake.configure()
        self.assertNotIn(self.tempdir, conanfile.path)

        # Automatic gcc
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "gcc"
        settings.compiler.version = "5.4"
        settings.arch = "x86"
        conanfile.settings = settings

        cmake = CMake(conanfile)
        cmake.configure()
        self.assertNotIn(self.tempdir, conanfile.path)

    def test_pkg_config_path(self):
        conanfile = ConanFileMock()
        conanfile.generators = ["pkg_config"]
        conanfile.folders.set_base_install("/my_install/folder/")
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"
        conanfile.settings = settings
        cmake = CMake(conanfile)
        cmake.configure()
        self.assertEqual(conanfile.captured_env["PKG_CONFIG_PATH"], "/my_install/folder/")

        conanfile.generators = []
        cmake = CMake(conanfile)
        cmake.configure()
        self.assertNotIn("PKG_CONFIG_PATH", conanfile.captured_env)

        cmake = CMake(conanfile)
        cmake.configure(pkg_config_paths=["reldir1", "/abspath2/to/other"])
        self.assertEqual(conanfile.captured_env["PKG_CONFIG_PATH"],
                         os.path.pathsep.join(["/my_install/folder/reldir1",
                                               "/abspath2/to/other"]))

        # If there is already a PKG_CONFIG_PATH do not set it
        conanfile.generators = ["pkg_config"]
        cmake = CMake(conanfile)
        with tools.environment_append({"PKG_CONFIG_PATH": "do_not_mess_with_this"}):
            cmake.configure()
            self.assertEqual(conanfile.captured_env["PKG_CONFIG_PATH"], "do_not_mess_with_this")

    def test_shared(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"
        settings.os = "Windows"

        conanfile = ConanFileMock(shared=True)
        conanfile.settings = settings
        cmake = CMake(conanfile)

        self.assertEqual(cmake.definitions["BUILD_SHARED_LIBS"], "ON")

        conanfile = ConanFileMock(shared=False)
        conanfile.settings = settings
        cmake = CMake(conanfile)

        self.assertEqual(cmake.definitions["BUILD_SHARED_LIBS"], "OFF")

        conanfile = ConanFileMock(shared=None)
        conanfile.settings = settings
        cmake = CMake(conanfile)

        self.assertNotIn("BUILD_SHARED_LIBS", cmake.definitions)

    def test_verbose(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"

        conanfile = ConanFileMock()
        conanfile.settings = settings
        cmake = CMake(conanfile)

        self.assertNotIn("CMAKE_VERBOSE_MAKEFILE", cmake.definitions)

        cmake.verbose = True
        self.assertEqual(cmake.definitions["CMAKE_VERBOSE_MAKEFILE"], "ON")

        cmake.verbose = False
        self.assertEqual(cmake.definitions["CMAKE_VERBOSE_MAKEFILE"], "OFF")

        cmake.definitions["CMAKE_VERBOSE_MAKEFILE"] = True
        self.assertTrue(cmake.verbose)

        cmake.definitions["CMAKE_VERBOSE_MAKEFILE"] = False
        self.assertFalse(cmake.verbose)

        del cmake.definitions["CMAKE_VERBOSE_MAKEFILE"]
        self.assertFalse(cmake.verbose)

    def test_set_toolset(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.compiler.toolset = "v140"  # Will be overwritten by parameter

        conanfile = ConanFileMock()
        conanfile.settings = settings

        cmake = CMake(conanfile, toolset="v141")
        self.assertIn('-T "v141"', cmake.command_line)

        # DEPRECATED VARIABLE, NOT MODIFY ANYMORE THE TOOLSET
        with tools.environment_append({"CONAN_CMAKE_TOOLSET": "v141"}):
            cmake = CMake(conanfile)
            self.assertNotIn('-T "v141"', cmake.command_line)

        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.compiler.toolset = "v140"

        conanfile = ConanFileMock()
        conanfile.settings = settings

        cmake = CMake(conanfile)
        self.assertIn('-T "v140"', cmake.command_line)

    @parameterized.expand([('Ninja',),
                           ('NMake Makefiles',),
                           ('NMake Makefiles JOM',)
                           ])
    def test_toolset_with_unsupported_generator(self, generator):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.compiler.toolset = "v140"

        conanfile = ConanFileMock()
        conanfile.settings = settings

        with self.assertRaises(ConanException):
            cmake = CMake(conanfile, generator=generator)
            _ = cmake.command_line

    def test_missing_settings(self):
        def instance_with_os_build(os_build):
            settings = Settings.loads(get_default_settings_yml())
            settings.os_build = os_build
            conanfile = ConanFileMock()
            conanfile.settings = settings
            return CMake(conanfile)

        cmake = instance_with_os_build("Linux")
        self.assertEqual(cmake.generator, "Unix Makefiles")

        cmake = instance_with_os_build("Macos")
        self.assertEqual(cmake.generator, "Unix Makefiles")

        cmake = instance_with_os_build("Windows")
        self.assertEqual(cmake.generator, None)

        with tools.environment_append({"CONAN_CMAKE_GENERATOR": "MyCoolGenerator"}):
            cmake = instance_with_os_build("Windows")
            self.assertEqual(cmake.generator, "MyCoolGenerator")

    def test_cmake_system_version_android(self):
        with tools.environment_append({"CONAN_CMAKE_SYSTEM_NAME": "SomeSystem",
                                       "CONAN_CMAKE_GENERATOR": "SomeGenerator"}):
            settings = Settings.loads(get_default_settings_yml())
            settings.os = "WindowsStore"
            settings.os.version = "8.1"

            conanfile = ConanFileMock()
            conanfile.settings = settings
            cmake = CMake(conanfile)
            self.assertEqual(cmake.definitions["CMAKE_SYSTEM_VERSION"], "8.1")

            settings = Settings.loads(get_default_settings_yml())
            settings.os = "Android"
            settings.os.api_level = "32"

            conanfile = ConanFileMock()
            conanfile.settings = settings
            cmake = CMake(conanfile)
            self.assertEqual(cmake.definitions["CMAKE_SYSTEM_VERSION"], "32")

    def test_install_definitions(self):
        conanfile = ConanFileMock()
        conanfile.folders.set_base_package(None)
        conanfile.settings = Settings.loads(get_default_settings_yml())
        install_defintions = {"CMAKE_INSTALL_PREFIX": conanfile.package_folder,
                              "CMAKE_INSTALL_BINDIR": "bin",
                              "CMAKE_INSTALL_SBINDIR": "bin",
                              "CMAKE_INSTALL_LIBEXECDIR": "bin",
                              "CMAKE_INSTALL_LIBDIR": "lib",
                              "CMAKE_INSTALL_INCLUDEDIR": "include",
                              "CMAKE_INSTALL_OLDINCLUDEDIR": "include",
                              "CMAKE_INSTALL_DATAROOTDIR": "share"}

        # Without package_folder
        cmake = CMake(conanfile)
        for key, value in cmake.definitions.items():
            self.assertNotIn(key, install_defintions.keys())

        # With package_folder
        conanfile.folders.set_base_package("my_package_folder")
        install_defintions["CMAKE_INSTALL_PREFIX"] = conanfile.package_folder
        cmake = CMake(conanfile)
        for key, value in install_defintions.items():
            self.assertEqual(cmake.definitions[key], value)

    @parameterized.expand([("Macos", "10.9",),
                           ("iOS", "7.0",),
                           ("watchOS", "4.0",),
                           ("tvOS", "11.0",)])
    @mock.patch("platform.system", return_value="Darwin")
    @mock.patch("conans.client.tools.apple.XCRun.sdk_path", return_value='/opt')
    def test_cmake_system_version_osx(self, the_os, os_version, _, __):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = the_os

        # No version defined
        conanfile = ConanFileMock()
        conanfile.settings = settings
        cmake = CMake(conanfile)
        self.assertFalse("CMAKE_OSX_DEPLOYMENT_TARGET" in cmake.definitions)
        if the_os == "Macos":
            self.assertFalse("CMAKE_SYSTEM_NAME" in cmake.definitions)
        else:
            self.assertTrue("CMAKE_SYSTEM_NAME" in cmake.definitions)
        self.assertFalse("CMAKE_SYSTEM_VERSION" in cmake.definitions)

        # Version defined using Conan env variable
        with tools.environment_append({"CONAN_CMAKE_SYSTEM_VERSION": "23"}):
            conanfile = ConanFileMock()
            conanfile.settings = settings
            cmake = CMake(conanfile)
            self.assertEqual(cmake.definitions["CMAKE_SYSTEM_VERSION"], "23")
            self.assertEqual(cmake.definitions["CMAKE_OSX_DEPLOYMENT_TARGET"], "23")

        # Version defined in settings
        settings.os.version = os_version
        conanfile = ConanFileMock()
        conanfile.settings = settings
        cmake = CMake(conanfile)
        self.assertEqual(cmake.definitions["CMAKE_SYSTEM_VERSION"], os_version)
        self.assertEqual(cmake.definitions["CMAKE_OSX_DEPLOYMENT_TARGET"], os_version)

        # Version defined in settings AND using Conan env variable
        with tools.environment_append({"CONAN_CMAKE_SYSTEM_VERSION": "23"}):
            conanfile = ConanFileMock()
            conanfile.settings = settings
            cmake = CMake(conanfile)
            self.assertEqual(cmake.definitions["CMAKE_SYSTEM_VERSION"], "23")
            self.assertEqual(cmake.definitions["CMAKE_OSX_DEPLOYMENT_TARGET"], "23")

    @staticmethod
    def scape(args):
        pattern = "%s" if sys.platform == "win32" else r"'%s'"
        return ' '.join(pattern % i for i in args.split())

    @parameterized.expand([('Ninja', 'Visual Studio', 15),
                           ('NMake Makefiles', 'Visual Studio', 15),
                           ('NMake Makefiles JOM', 'Visual Studio', 15),
                           ('Ninja', 'clang', 6.0),
                           ('NMake Makefiles', 'clang', 6.0),
                           ('NMake Makefiles JOM', 'clang', 6.0)
                           ])
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows vcvars")
    def test_vcvars_applied(self, generator, compiler, version):
        conanfile = ConanFileMock()
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = compiler
        settings.compiler.version = version
        conanfile.settings = settings

        cmake = CMake(conanfile, generator=generator)

        with mock.patch("conans.client.tools.vcvars_dict") as vcvars_mock:
            vcvars_mock.__enter__ = mock.MagicMock(return_value=(mock.MagicMock(), None))
            vcvars_mock.__exit__ = mock.MagicMock(return_value=None)
            cmake.configure()
            self.assertTrue(vcvars_mock.called, "vcvars weren't called")

        with mock.patch("conans.client.tools.vcvars_dict") as vcvars_mock:
            vcvars_mock.__enter__ = mock.MagicMock(return_value=(mock.MagicMock(), None))
            vcvars_mock.__exit__ = mock.MagicMock(return_value=None)
            cmake.build()
            self.assertTrue(vcvars_mock.called, "vcvars weren't called")

    @parameterized.expand([('Ninja',),
                           ('NMake Makefiles',),
                           ('NMake Makefiles JOM',),
                           ('Unix Makefiles',),
                           ])
    def test_intel_compilervars_applied(self, generator):
        conanfile = ConanFileMock()
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "intel"
        settings.arch = "x86_64"
        settings.compiler.version = "19"
        conanfile.settings = settings

        cmake = CMake(conanfile, generator=generator)

        with mock.patch("conans.client.tools.intel_compilervars_dict") as cvars_mock:
            cvars_mock.__enter__ = mock.MagicMock(return_value=(mock.MagicMock(), None))
            cvars_mock.__exit__ = mock.MagicMock(return_value=None)
            cmake.configure()
            self.assertTrue(cvars_mock.called, "intel_compilervars weren't called")

        with mock.patch("conans.client.tools.intel_compilervars_dict") as cvars_mock:
            cvars_mock.__enter__ = mock.MagicMock(return_value=(mock.MagicMock(), None))
            cvars_mock.__exit__ = mock.MagicMock(return_value=None)
            cmake.build()
            self.assertTrue(cvars_mock.called, "intel_compilervars weren't called")

    def test_cmake_program(self):
        conanfile = ConanFileMock()
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "14"
        conanfile.settings = settings

        cmake = CMake(conanfile, parallel=False)
        cmake.build()
        self.assertEqual("cmake --build %s" % CMakeTest.scape("."), conanfile.command)

        cmake = CMake(conanfile, cmake_program="use_another_cmake", parallel=False)
        cmake.build()
        self.assertEqual("use_another_cmake --build %s" % CMakeTest.scape("."), conanfile.command)

        with tools.environment_append({"CONAN_CMAKE_PROGRAM": "my_custom_cmake"}):
            cmake = CMake(conanfile, parallel=False)
            cmake.build()
            self.assertEqual("my_custom_cmake --build %s" % CMakeTest.scape("."), conanfile.command)

        with tools.environment_append({
            "CONAN_CMAKE_PROGRAM": "cmake_from_environment_has_priority"
        }):
            cmake = CMake(conanfile, cmake_program="but_not_cmake_from_the_ctor", parallel=False)
            cmake.build()
            self.assertEqual("cmake_from_environment_has_priority --build %s" % CMakeTest.scape("."),
                             conanfile.command)

    def test_msbuild_verbosity(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "10"
        settings.compiler.runtime = "MDd"
        settings.arch = "x86"
        settings.build_type = None

        conanfile = ConanFileMock()
        conanfile.settings = settings

        cmake = CMake(conanfile)
        cmake.build()
        self.assertIn("/verbosity:minimal", conanfile.command)

        cmake = CMake(conanfile, msbuild_verbosity="quiet")
        cmake.build()
        self.assertIn("/verbosity:quiet", conanfile.command)

        cmake = CMake(conanfile, msbuild_verbosity=None)
        cmake.build()
        self.assertNotIn("/verbosity", conanfile.command)

        with tools.environment_append({"CONAN_MSBUILD_VERBOSITY": "detailed"}):
            cmake = CMake(conanfile)
            cmake.build()
            self.assertIn("/verbosity:detailed", conanfile.command)

    def test_ctest_variables(self):
        conanfile = ConanFileMock()
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "14"
        conanfile.settings = settings

        cmake = CMake(conanfile, parallel=False, generator="NMake Makefiles")
        cmake.test()
        self.assertEqual(conanfile.captured_env["CTEST_OUTPUT_ON_FAILURE"], "0")
        self.assertNotIn("CTEST_PARALLEL_LEVEL", conanfile.captured_env)

        with tools.environment_append({"CONAN_CPU_COUNT": "666"}):
            cmake = CMake(conanfile, parallel=True, generator="NMake Makefiles")
            cmake.test(output_on_failure=True)
            self.assertEqual(conanfile.captured_env["CTEST_OUTPUT_ON_FAILURE"], "1")
            self.assertEqual(conanfile.captured_env["CTEST_PARALLEL_LEVEL"], "666")

    def test_unkown_generator_does_not_raise(self):
        # https://github.com/conan-io/conan/issues/4265
        settings = MockSettings({"os_build": "Windows", "compiler": "random",
                                 "compiler.version": "15", "build_type": "Release"})
        conanfile = ConanFileMock()
        conanfile.settings = settings
        cmake = CMake(conanfile)
        self.assertIsNone(cmake.generator)
        self.assertIn("WARN: CMake generator could not be deduced from settings", conanfile.output)
        cmake.configure()
        cmake.build()

    def test_cmake_system_version_windowsce(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "WindowsCE"
        settings.os.version = "8.0"

        conanfile = ConanFileMock()
        conanfile.settings = settings
        cmake = CMake(conanfile)
        self.assertEqual(cmake.definitions["CMAKE_SYSTEM_VERSION"], "8.0")

    def test_cmake_vs_arch(self):
        settings = Settings.loads(get_default_settings_yml())
        settings.os = "Windows"
        settings.arch = "x86_64"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"

        conanfile = ConanFileMock()
        conanfile.settings = settings

        cmake = CMake(conanfile, generator="Visual Studio 15 2017 Win64", toolset="v141,host=x64")
        self.assertIn('-G "Visual Studio 15 2017 Win64"', cmake.command_line)
        self.assertIn('-T "v141,host=x64"', cmake.command_line)

        cmake = CMake(conanfile, generator="Visual Studio 15 2017", generator_platform="x64",
                      toolset="v141,host=x64")
        self.assertIn('-G "Visual Studio 15 2017 Win64"', cmake.command_line)
        self.assertIn('-T "v141,host=x64"', cmake.command_line)

    def test_skip_test(self):
        conf = ConfDefinition()
        conf.loads("tools.build:skip_test=1")
        conanfile = ConanFileMock()
        conanfile.settings = Settings()
        conanfile.conf = conf.get_conanfile_conf(None)
        cmake = CMake(conanfile, generator="Unix Makefiles")
        cmake.test()
        self.assertIsNone(conanfile.command)
