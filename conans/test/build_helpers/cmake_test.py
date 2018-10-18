import os
import shutil
import stat
import sys
import unittest
import platform
import mock

from collections import namedtuple

from conans import tools
from conans.model.conan_file import ConanFile
from conans.model.ref import ConanFileReference
from conans.model.build_info import CppInfo, DepsCppInfo
from conans.model.settings import Settings
from conans.client.conf import default_settings_yml
from conans.client.build.cmake import CMake
from conans.client.build.cmake_flags import cmake_in_local_cache_var_name
from conans.test.utils.tools import TestBufferConanOutput
from conans.tools import cpu_count
from conans.util.files import save, load
from conans.test.utils.test_files import temp_folder
from conans.model.options import Options, PackageOptions
from conans.errors import ConanException


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

    def config_patch_test(self):

        conan_file = ConanFileMock()
        conan_file.name = "MyPkg"
        conan_file.settings = Settings()
        conan_file.source_folder = os.path.join(self.tempdir, "src")
        conan_file.build_folder = os.path.join(self.tempdir, "build")
        conan_file.package_folder = os.path.join(self.tempdir, "pkg")
        conan_file.deps_cpp_info = DepsCppInfo()

        msg = "FOLDER: " + _format_path_as_cmake(conan_file.package_folder)
        for folder in (conan_file.build_folder, conan_file.package_folder):
            save(os.path.join(folder, "file1.cmake"), "Nothing")
            save(os.path.join(folder, "file2"), msg)
            save(os.path.join(folder, "file3.txt"), msg)
            save(os.path.join(folder, "file3.cmake"), msg)
            save(os.path.join(folder, "sub", "file3.cmake"), msg)

        cmake = CMake(conan_file, generator="Unix Makefiles")
        cmake.patch_config_paths()
        for folder in (conan_file.build_folder, conan_file.package_folder):
            self.assertEqual("Nothing", load(os.path.join(folder, "file1.cmake")))
            self.assertEqual(msg, load(os.path.join(folder, "file2")))
            self.assertEqual(msg, load(os.path.join(folder, "file3.txt")))
            self.assertEqual("FOLDER: ${CONAN_MYPKG_ROOT}",
                             load(os.path.join(folder, "file3.cmake")))
            self.assertEqual("FOLDER: ${CONAN_MYPKG_ROOT}",
                             load(os.path.join(folder, "sub", "file3.cmake")))

    def config_patch_deps_test(self):
        conan_file = ConanFileMock()
        conan_file.name = "MyPkg"
        conan_file.settings = Settings()
        conan_file.source_folder = os.path.join(self.tempdir, "src")
        conan_file.build_folder = os.path.join(self.tempdir, "build")
        conan_file.package_folder = os.path.join(self.tempdir, "pkg")
        conan_file.deps_cpp_info = DepsCppInfo()

        ref = ConanFileReference.loads("MyPkg1/0.1@user/channel")
        cpp_info = CppInfo(self.tempdir2)
        conan_file.deps_cpp_info.update(cpp_info, ref.name)
        self.tempdir = temp_folder(path_with_spaces=False)

        self.assertEqual(list(conan_file.deps_cpp_info.deps), ['MyPkg1'])
        self.assertEqual(conan_file.deps_cpp_info['MyPkg1'].rootpath,
                         self.tempdir2)

        msg = "FOLDER: " + _format_path_as_cmake(self.tempdir2)
        for folder in (conan_file.build_folder, conan_file.package_folder):
            save(os.path.join(folder, "file1.cmake"), "Nothing")
            save(os.path.join(folder, "file2"), msg)
            save(os.path.join(folder, "file3.txt"), msg)
            save(os.path.join(folder, "file3.cmake"), msg)
            save(os.path.join(folder, "sub", "file3.cmake"), msg)

        cmake = CMake(conan_file, generator="Unix Makefiles")
        cmake.patch_config_paths()
        for folder in (conan_file.build_folder, conan_file.package_folder):
            self.assertEqual("Nothing", load(os.path.join(folder, "file1.cmake")))
            self.assertEqual(msg, load(os.path.join(folder, "file2")))
            self.assertEqual(msg, load(os.path.join(folder, "file3.txt")))
            self.assertEqual("FOLDER: ${CONAN_MYPKG1_ROOT}",
                             load(os.path.join(folder, "file3.cmake")))
            self.assertEqual("FOLDER: ${CONAN_MYPKG1_ROOT}",
                             load(os.path.join(folder, "sub", "file3.cmake")))

    def partial_build_test(self):
        conan_file = ConanFileMock()
        conan_file.settings = Settings()
        conan_file.should_configure = False
        conan_file.should_build = False
        conan_file.should_install = False
        conan_file.should_test = False
        cmake = CMake(conan_file, generator="Unix Makefiles")
        cmake.configure()
        self.assertIsNone(conan_file.command)
        cmake.build()
        self.assertIsNone(conan_file.command)
        cmake.install()
        self.assertIsNone(conan_file.command)
        conan_file.name = None
        cmake.patch_config_paths()
        cmake.test()
        self.assertIsNone(conan_file.command)

    def should_flags_test(self):
        conanfile = ConanFileMock()
        conanfile.settings = Settings()
        conanfile.should_configure = False
        conanfile.should_build = True
        conanfile.should_install = False
        conanfile.should_test = True
        conanfile.package_folder = temp_folder()
        cmake = CMake(conanfile, generator="Unix Makefiles")
        cmake.configure()
        self.assertIsNone(conanfile.command)
        cmake.build()
        self.assertIn("cmake --build %s" % CMakeTest.scape(". -- -j%i" % cpu_count()),
                      conanfile.command)
        cmake.install()
        self.assertNotIn("cmake --build %s" % CMakeTest.scape(". --target install -- -j%i"
                                                              % cpu_count()), conanfile.command)
        cmake.test()
        self.assertIn("cmake --build %s" % CMakeTest.scape(". --target test -- -j%i" % cpu_count()),
                      conanfile.command)
        conanfile.should_build = False
        cmake.configure()
        self.assertNotIn("cd . && cmake", conanfile.command)
        cmake.build()
        self.assertNotIn("cmake --build %s" % CMakeTest.scape(". -- -j%i" % cpu_count()),
                         conanfile.command)
        cmake.install()
        self.assertNotIn("cmake --build %s" % CMakeTest.scape(". --target install -- -j%i"
                                                              % cpu_count()), conanfile.command)
        cmake.test()
        self.assertIn("cmake --build %s" % CMakeTest.scape(". --target test -- -j%i" % cpu_count()),
                      conanfile.command)
        conanfile.should_install = True
        conanfile.should_test = False
        cmake.configure()
        self.assertNotIn("cd . && cmake", conanfile.command)
        cmake.build()
        self.assertNotIn("cmake --build %s" % CMakeTest.scape(". -- -j%i" % cpu_count()),
                         conanfile.command)
        cmake.install()
        self.assertIn("cmake --build %s" % CMakeTest.scape(". --target install -- -j%i"
                                                           % cpu_count()), conanfile.command)
        cmake.test()
        self.assertNotIn("cmake --build %s" % CMakeTest.scape(". --target test -- -j%i"
                                                              % cpu_count()), conanfile.command)

    def cmake_generator_test(self):
        conan_file = ConanFileMock()
        conan_file.settings = Settings()
        with tools.environment_append({"CONAN_CMAKE_GENERATOR": "My CMake Generator"}):
            cmake = CMake(conan_file)
            self.assertIn('-G "My CMake Generator"', cmake.command_line)

    def cmake_fpic_test(self):
        settings = Settings.loads(default_settings_yml)
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

            conan_file = ConanFileMock(options='{%s}' % ", ".join(options),
                                       options_values=values)
            conan_file.settings = the_settings
            cmake = CMake(conan_file)
            cmake.configure()
            if expected_option is not None:
                self.assertEquals(cmake.definitions["CONAN_CMAKE_POSITION_INDEPENDENT_CODE"],
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
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86_64"

        assert_fpic(settings, input_shared=True, input_fpic=True, expected_option=None)

    def cmake_make_program_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "6.3"
        settings.arch = "x86"
        settings.build_type = "Release"
        conan_file = ConanFileMock()
        conan_file.settings = settings
        conan_file.source_folder = os.path.join(self.tempdir, "my_cache_source_folder")
        conan_file.build_folder = os.path.join(self.tempdir, "my_cache_build_folder")

        # Existing make
        make_path = os.path.join(self.tempdir, "make")
        save(make_path, "")
        st = os.stat(make_path)
        os.chmod(make_path, st.st_mode | stat.S_IEXEC)
        with tools.environment_append({"CONAN_MAKE_PROGRAM": make_path}):
            cmake = CMake(conan_file)
            self.assertEquals(cmake.definitions["CMAKE_MAKE_PROGRAM"], make_path)

        # Not existing make
        with tools.environment_append({"CONAN_MAKE_PROGRAM": "fake_path/make"}):
            cmake = CMake(conan_file)
            self.assertNotIn("CMAKE_MAKE_PROGRAM", cmake.definitions)
            self.assertIn("The specified make program 'fake_path/make' cannot be found",
                          conan_file.output)

    def folders_test(self):
        def quote_var(var):
            return "'%s'" % var if platform.system() != "Windows" else var

        settings = Settings.loads(default_settings_yml)
        settings.os = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "6.3"
        settings.arch = "x86"
        settings.build_type = "Release"

        conan_file = ConanFileMock()
        conan_file.settings = settings
        conan_file.source_folder = os.path.join(self.tempdir, "my_cache_source_folder")
        conan_file.build_folder = os.path.join(self.tempdir, "my_cache_build_folder")
        with tools.chdir(self.tempdir):
            linux_stuff = '-DCMAKE_SYSTEM_NAME="Linux" ' \
                          '-DCMAKE_SYSROOT="/path/to/sysroot" ' \
                          if platform.system() != "Linux" else ""
            generator = "MinGW Makefiles" if platform.system() == "Windows" else "Unix Makefiles"

            flags = '-DCONAN_EXPORTED="1"{} -DCONAN_COMPILER="gcc" ' \
                    '-DCONAN_COMPILER_VERSION="6.3" ' \
                    '-DCONAN_CXX_FLAGS="-m32" -DCONAN_SHARED_LINKER_FLAGS="-m32" ' \
                    '-DCONAN_C_FLAGS="-m32" -DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON"'
            flags_in_local_cache = flags.format(' -D' + cmake_in_local_cache_var_name + '="ON"')
            flags_no_local_cache = flags.format(' -D' + cmake_in_local_cache_var_name + '="OFF"')

            base_cmd = 'cmake -G "{generator}" -DCMAKE_BUILD_TYPE="Release" {linux_stuff}' \
                       '{{flags}} -Wno-dev'
            base_cmd = base_cmd.format(generator=generator, linux_stuff=linux_stuff)
            full_cmd = "cd {build_expected} && {base_cmd} {source_expected}"

            build_expected = quote_var("build")
            source_expected = quote_var("../subdir")

            cmake = CMake(conan_file)
            cmake.configure(source_dir="../subdir", build_dir="build")
            self.assertEquals(conan_file.command,
                              full_cmd.format(build_expected=build_expected,
                                              source_expected=source_expected,
                                              base_cmd=base_cmd.format(flags=flags_no_local_cache)))

            cmake = CMake(conan_file)
            cmake.configure(build_dir="build")
            build_expected = quote_var("build")
            source_expected = quote_var(os.path.join(self.tempdir, "my_cache_source_folder"))
            self.assertEquals(conan_file.command,
                              full_cmd.format(build_expected=build_expected,
                                              source_expected=source_expected,
                                              base_cmd=base_cmd.format(flags=flags_no_local_cache)))

            cmake = CMake(conan_file)
            cmake.configure()
            build_expected = quote_var(os.path.join(self.tempdir, "my_cache_build_folder"))
            source_expected = quote_var(os.path.join(self.tempdir, "my_cache_source_folder"))
            self.assertEquals(conan_file.command,
                              full_cmd.format(build_expected=build_expected,
                                              source_expected=source_expected,
                                              base_cmd=base_cmd.format(flags=flags_no_local_cache)))

            cmake = CMake(conan_file)
            cmake.configure(source_folder="source", build_folder="build")
            build_expected = quote_var(os.path.join(os.path.join(self.tempdir,
                                                                 "my_cache_build_folder", "build")))
            source_expected = quote_var(os.path.join(os.path.join(self.tempdir,
                                                                  "my_cache_source_folder",
                                                                  "source")))
            self.assertEquals(conan_file.command,
                              full_cmd.format(build_expected=build_expected,
                                              source_expected=source_expected,
                                              base_cmd=base_cmd.format(flags=flags_no_local_cache)))

            conan_file.in_local_cache = True
            cmake = CMake(conan_file)
            cmake.configure(source_folder="source", build_folder="build",
                            cache_build_folder="rel_only_cache")
            build_expected = quote_var(os.path.join(self.tempdir, "my_cache_build_folder",
                                                    "rel_only_cache"))
            source_expected = quote_var(os.path.join(self.tempdir, "my_cache_source_folder",
                                                     "source"))
            self.assertEquals(conan_file.command,
                              full_cmd.format(build_expected=build_expected,
                                              source_expected=source_expected,
                                              base_cmd=base_cmd.format(flags=flags_in_local_cache)))

            conan_file.in_local_cache = False
            cmake = CMake(conan_file)
            cmake.configure(source_folder="source", build_folder="build",
                            cache_build_folder="rel_only_cache")
            build_expected = quote_var(os.path.join(self.tempdir, "my_cache_build_folder", "build"))
            source_expected = quote_var(os.path.join(self.tempdir, "my_cache_source_folder",
                                                     "source"))
            self.assertEquals(conan_file.command,
                              full_cmd.format(build_expected=build_expected,
                                              source_expected=source_expected,
                                              base_cmd=base_cmd.format(flags=flags_no_local_cache)))

            conan_file.in_local_cache = True
            cmake = CMake(conan_file)
            cmake.configure(build_dir="build", cache_build_folder="rel_only_cache")
            build_expected = quote_var(os.path.join(self.tempdir, "my_cache_build_folder",
                                                    "rel_only_cache"))
            source_expected = quote_var(os.path.join(self.tempdir, "my_cache_source_folder"))
            self.assertEquals(conan_file.command,
                              full_cmd.format(build_expected=build_expected,
                                              source_expected=source_expected,
                                              base_cmd=base_cmd.format(flags=flags_in_local_cache)))

            # Raise mixing
            with self.assertRaisesRegexp(ConanException, "Use 'build_folder'/'source_folder'"):
                cmake = CMake(conan_file)
                cmake.configure(source_folder="source", build_dir="build")

    def build_type_ovewrite_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Linux"
        settings.compiler = "gcc"
        settings.compiler.version = "6.3"
        settings.arch = "x86"
        settings.build_type = "Release"
        conan_file = ConanFileMock()
        conan_file.settings = settings
        cmake = CMake(conan_file)
        cmake.build_type = "Debug"
        self.assertIn('WARN: Set CMake build type "Debug" is different than the '
                      'settings build_type "Release"', conan_file.output)
        self.assertEquals(cmake.build_type, "Debug")
        self.assertIn('-DCMAKE_BUILD_TYPE="Debug"', cmake.command_line)

        conan_file = ConanFileMock()
        conan_file.settings = settings
        cmake = CMake(conan_file)
        self.assertNotIn('WARN: Set CMake build type ', conan_file.output)
        self.assertEquals(cmake.build_type, "Release")

        # Now with visual, (multiconfig)
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.build_type = "Release"
        conan_file = ConanFileMock()
        conan_file.settings = settings
        cmake = CMake(conan_file)
        cmake.build_type = "Debug"
        self.assertIn('WARN: Set CMake build type "Debug" is different than the '
                      'settings build_type "Release"', conan_file.output)
        self.assertEquals(cmake.build_type, "Debug")
        self.assertNotIn('-DCMAKE_BUILD_TYPE="Debug"', cmake.command_line)
        self.assertIn("--config Debug", cmake.build_config)
        cmake = CMake(conan_file)
        cmake.build_type = "Release"
        self.assertIn("--config Release", cmake.build_config)

    def loads_default_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"
        conan_file = ConanFileMock()
        conan_file.settings = settings

        def check(text, build_config, generator=None, set_cmake_flags=False):
            os = str(settings.os)
            os_ver = str(settings.os.version) if settings.get_safe('os.version') else None
            for cmake_system_name in (True, False):
                cross_ver = ("-DCMAKE_SYSTEM_VERSION=\"%s\" " % os_ver) if os_ver else ""
                cross = ("-DCMAKE_SYSTEM_NAME=\"%s\" %s-DCMAKE_SYSROOT=\"/path/to/sysroot\" "
                         % ({"Macos": "Darwin"}.get(os, os), cross_ver)
                         if (platform.system() != os and cmake_system_name) else "")
                cmake = CMake(conan_file, generator=generator, cmake_system_name=cmake_system_name,
                              set_cmake_flags=set_cmake_flags)
                new_text = text.replace("-DCONAN_EXPORTED", "%s-DCONAN_EXPORTED" % cross)
                if "Visual Studio" in text:
                    cores = ('-DCONAN_CXX_FLAGS="/MP{0}" '
                             '-DCONAN_C_FLAGS="/MP{0}" '.format(tools.cpu_count()))
                    new_text = new_text.replace('-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON"',
                                                '%s-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON"' % cores)

                self.assertEqual(new_text, cmake.command_line)
                self.assertEqual(build_config, cmake.build_config)

        check('-G "Visual Studio 12 2013" -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev',
              "")

        check('-G "Custom Generator" -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev',
              '', generator="Custom Generator")

        check('-G "Custom Generator" -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev',
              '', generator="Custom Generator", set_cmake_flags=True)

        settings.build_type = "Debug"
        check('-G "Visual Studio 12 2013" -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev',
              '--config Debug')

        settings.arch = "x86_64"
        check('-G "Visual Studio 12 2013 Win64" -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev',
              '--config Debug')

        settings.compiler = "gcc"
        settings.compiler.version = "4.8"
        generator = "MinGW Makefiles" if platform.system() == "Windows" else "Unix Makefiles"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug" -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="gcc" -DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev' % generator, "")

        settings.os = "Linux"
        settings.arch = "x86"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug"'
              ' -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="gcc" '
              '-DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS="-m32" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m32" -DCONAN_C_FLAGS="-m32" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev' % generator,
              "")

        settings.arch = "x86_64"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug"'
              ' -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="gcc" '
              '-DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev' % generator,
              "")

        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug"'
              ' -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="gcc" '
              '-DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" '
              '-DCMAKE_CXX_FLAGS="-m64" -DCMAKE_SHARED_LINKER_FLAGS="-m64" -DCMAKE_C_FLAGS="-m64" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" '
              '-Wno-dev' % generator,
              "", set_cmake_flags=True)

        settings.os = "FreeBSD"
        settings.compiler = "clang"
        settings.compiler.version = "3.8"
        settings.arch = "x86"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug"'
              ' -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="clang" '
              '-DCONAN_COMPILER_VERSION="3.8" -DCONAN_CXX_FLAGS="-m32" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m32" -DCONAN_C_FLAGS="-m32" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev' % generator,
              "")

        settings.arch = "x86_64"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug"'
              ' -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="clang" '
              '-DCONAN_COMPILER_VERSION="3.8" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev' % generator,
              "")

        settings.os = "SunOS"
        settings.compiler = "sun-cc"
        settings.compiler.version = "5.10"
        settings.arch = "x86"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug"'
              ' -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS="-m32" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m32" -DCONAN_C_FLAGS="-m32" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev' % generator,
              "")

        settings.arch = "x86_64"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug"'
              ' -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" -DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev' % generator,
              "")

        settings.arch = "sparc"

        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug" -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS="-m32" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m32" -DCONAN_C_FLAGS="-m32" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev' % generator,
              "")

        settings.arch = "sparcv9"
        check('-G "%s" -DCMAKE_BUILD_TYPE="Debug" -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev' % generator,
              "")

        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.os = "WindowsStore"
        settings.os.version = "8.1"
        settings.build_type = "Debug"
        check('-G "Visual Studio 12 2013" -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev',
              "--config Debug")

        settings.os.version = "10.0"
        check('-G "Visual Studio 12 2013" -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
              '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev',
              "--config Debug")

    def deleted_os_test(self):
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
        conan_file = ConanFileMock()
        conan_file.settings = settings

        cmake = CMake(conan_file)
        generator = "Unix" if platform.system() != "Windows" else "MinGW"
        cross = ("-DCMAKE_SYSTEM_NAME=\"Linux\" -DCMAKE_SYSROOT=\"/path/to/sysroot\" "
                 if platform.system() != "Linux" else "")
        self.assertEqual('-G "%s Makefiles" %s-DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" '
                         '-DCONAN_COMPILER="gcc" '
                         '-DCONAN_COMPILER_VERSION="4.9" -DCONAN_CXX_FLAGS="-m64" '
                         '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" '
                         '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" -Wno-dev' % (generator, cross),
                         cmake.command_line)

    def test_sysroot(self):
        settings = Settings.loads(default_settings_yml)
        conan_file = ConanFileMock()
        conan_file.settings = settings
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"
        settings.os = "Windows"
        cmake = CMake(conan_file)
        if platform.system() == "Windows":
            self.assertNotIn("-DCMAKE_SYSROOT=", cmake.flags)

        # Now activate cross build and check sysroot and system processor
        with(tools.environment_append({"CONAN_CMAKE_SYSTEM_NAME": "Android",
                                       "CONAN_CMAKE_SYSTEM_PROCESSOR": "somevalue"})):
            cmake = CMake(conan_file)
            self.assertEquals(cmake.definitions["CMAKE_SYSROOT"], "/path/to/sysroot")
            self.assertEquals(cmake.definitions["CMAKE_SYSTEM_PROCESSOR"], "somevalue")

    def test_deprecated_behaviour(self):
        """"Remove when deprecate the old settings parameter to CMake and
        conanfile to configure/build/test"""
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        conan_file = ConanFileMock()
        conan_file.settings = settings
        with self.assertRaises(ConanException):
            CMake(settings)

    def test_cores_ancient_visual(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "9"
        settings.compiler.runtime = "MDd"
        settings.arch = "x86"
        settings.build_type = None

        conan_file = ConanFileMock()
        conan_file.settings = settings
        cmake = CMake(conan_file)

        cmake.build()
        self.assertNotIn("/m", conan_file.command)

        settings.compiler.version = "10"
        cmake = CMake(conan_file)

        cmake.build()
        self.assertIn("/m", conan_file.command)

    def convenient_functions_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Android"
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

        conan_file = ConanFileMock()
        conan_file.settings = settings
        cmake = CMake(conan_file)

        cross = '-DCMAKE_SYSTEM_NAME="Android"' \
                ' -DCMAKE_SYSROOT="/path/to/sysroot"' \
                ' -DCMAKE_ANDROID_ARCH_ABI="armeabi-v7a"'
        target_test = CMakeTest.scape('--target test')

        cmake.configure()

        self.assertEqual('cd {0} && cmake -G "MinGW Makefiles" '
                         '{1} -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF"'
                         ' -DCONAN_COMPILER="gcc" -DCONAN_COMPILER_VERSION="5.4"'
                         ' -DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON"'
                         ' -Wno-dev {0}'.format(dot_dir, cross),
                         conan_file.command)

        cmake.build()
        self.assertEqual('cmake --build %s %s' %
                         (dot_dir, (CMakeTest.scape('-- -j%i' % cpu_count()))), conan_file.command)

        cmake.test()
        self.assertEqual('cmake --build %s %s %s' %
                         (dot_dir, target_test, (CMakeTest.scape('-- -j%i' % cpu_count()))),
                         conan_file.command)

        settings.build_type = "Debug"
        cmake = CMake(conan_file)
        cmake.build()
        self.assertEqual('cmake --build %s %s' %
                         (dot_dir, (CMakeTest.scape('-- -j%i' % cpu_count()))), conan_file.command)

        cmake.test()
        self.assertEqual('cmake --build %s %s %s' %
                         (dot_dir, target_test, (CMakeTest.scape('-- -j%i' % cpu_count()))),
                         conan_file.command)

        cmake.configure(source_dir="/source", build_dir=self.tempdir,
                        args=['--foo "bar"'], defs={"SHARED": True})
        if sys.platform == 'win32':
            escaped_args = r'"--foo \"bar\"" -DSHARED="True" /source'
        else:
            escaped_args = "'--foo \"bar\"' -DSHARED=\"True\" '/source'"

        self.assertEqual('cd %s && cmake -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE="Debug" '
                         '%s -DCONAN_EXPORTED="1" -DCONAN_IN_LOCAL_CACHE="OFF" '
                         '-DCONAN_COMPILER="gcc" -DCONAN_COMPILER_VERSION="5.4" '
                         '-DCMAKE_EXPORT_NO_PACKAGE_REGISTRY="ON" '
                         '-Wno-dev %s' % (tempdir, cross, escaped_args),
                         conan_file.command)

        cmake.build(args=["--bar 'foo'"], target="install")
        if platform.system() == 'Windows':
            escaped_args = '--target install "--bar \'foo\'"'
        else:
            escaped_args = r"'--target' 'install' '--bar '\''foo'\'''"
        self.assertEqual('cmake --build %s %s %s'
                         % (tempdir, escaped_args, (CMakeTest.scape('-- -j%i' % cpu_count()))),
                         conan_file.command)

        cmake.test(args=["--bar 'foo'"])
        if sys.platform == 'win32':
            escaped_args = '%s "--bar \'foo\'"' % target_test
        else:
            escaped_args = r"%s '--bar '\''foo'\'''" % target_test
        self.assertEqual('cmake --build %s %s %s' %
                         (tempdir, escaped_args, (CMakeTest.scape('-- -j%i' % cpu_count()))),
                         conan_file.command)

        settings.build_type = "Release"
        cmake = CMake(conan_file)
        cmake.build()
        self.assertEqual('cmake --build %s %s' %
                         (dot_dir, (CMakeTest.scape('-- -j%i' % cpu_count()))),
                         conan_file.command)

        cmake.test()
        self.assertEqual('cmake --build %s %s %s'
                         % (dot_dir, target_test, (CMakeTest.scape('-- -j%i' % cpu_count()))),
                         conan_file.command)

        cmake.build(build_dir=self.tempdir)
        self.assertEqual('cmake --build %s %s'
                         % (tempdir, (CMakeTest.scape('-- -j%i' % cpu_count()))),
                         conan_file.command)

        cmake.test(build_dir=self.tempdir)
        self.assertEqual('cmake --build %s %s %s'
                         % (tempdir, target_test, (CMakeTest.scape('-- -j%i' % cpu_count()))),
                         conan_file.command)

        settings.compiler = "gcc"
        settings.compiler.version = "5.4"
        cmake = CMake(conan_file)
        cmake.build()
        self.assertEqual('cmake --build %s' % (CMakeTest.scape('. -- -j%i' % cpu_count())),
                         conan_file.command)

        cmake.test()
        self.assertEqual('cmake --build '
                         '%s' % (CMakeTest.scape('. --target test -- -j%i' % cpu_count())),
                         conan_file.command)

        cmake.build(args=['foo', '--', 'bar'])
        self.assertEqual('cmake --build %s' % (CMakeTest.scape('. foo -- bar -j%i' % cpu_count())),
                         conan_file.command)

        cmake.test(args=['foo', '--', 'bar'])
        self.assertEqual('cmake --build '
                         '%s' % (CMakeTest.scape('. --target test foo -- bar -j%i' % cpu_count())),
                         conan_file.command)

        cmake = CMake(conan_file, parallel=False)
        cmake.build()
        self.assertEqual('cmake --build %s' % CMakeTest.scape('.'), conan_file.command)

        cmake.test()
        self.assertEqual('cmake --build %s' % CMakeTest.scape('. --target test'),
                         conan_file.command)

    def test_run_tests(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "14"
        settings.compiler.runtime = "MDd"
        settings.arch = "x86"
        settings.build_type = None

        conan_file = ConanFileMock()
        conan_file.settings = settings
        cmake = CMake(conan_file)
        cmake.test()
        self.assertIn('cmake --build '
                      '%s' % CMakeTest.scape('. --target RUN_TESTS -- /m:%i' % cpu_count()),
                      conan_file.command)

        cmake.generator = "Ninja Makefiles"
        cmake.test()
        self.assertEqual('cmake --build '
                         '%s' % CMakeTest.scape('. --target test -- -j%i' % cpu_count()),
                         conan_file.command)

        cmake.generator = "NMake Makefiles"
        cmake.test()
        self.assertEqual('cmake --build '
                         '%s' % CMakeTest.scape('. --target test'),
                         conan_file.command)

    def test_clean_sh_path(self):

        if platform.system() != "Windows":
            return

        os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + self.tempdir
        save(os.path.join(self.tempdir, "sh.exe"), "Fake sh")
        conanfile = ConanFileMock()
        settings = Settings.loads(default_settings_yml)
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
        settings = Settings.loads(default_settings_yml)
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
        conanfile.install_folder = "/my_install/folder/"
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"
        conanfile.settings = settings
        cmake = CMake(conanfile)
        cmake.configure()
        self.assertEquals(conanfile.captured_env["PKG_CONFIG_PATH"], "/my_install/folder/")

        conanfile.generators = []
        cmake = CMake(conanfile)
        cmake.configure()
        self.assertNotIn("PKG_CONFIG_PATH", conanfile.captured_env)

        cmake = CMake(conanfile)
        cmake.configure(pkg_config_paths=["reldir1", "/abspath2/to/other"])
        self.assertEquals(conanfile.captured_env["PKG_CONFIG_PATH"],
                          os.path.pathsep.join(["/my_install/folder/reldir1",
                                                "/abspath2/to/other"]))

        # If there is already a PKG_CONFIG_PATH do not set it
        conanfile.generators = ["pkg_config"]
        cmake = CMake(conanfile)
        with tools.environment_append({"PKG_CONFIG_PATH": "do_not_mess_with_this"}):
            cmake.configure()
            self.assertEquals(conanfile.captured_env["PKG_CONFIG_PATH"], "do_not_mess_with_this")

    def test_shared(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"
        settings.os = "Windows"

        conan_file = ConanFileMock(shared=True)
        conan_file.settings = settings
        cmake = CMake(conan_file)

        self.assertEquals(cmake.definitions["BUILD_SHARED_LIBS"], "ON")

        conan_file = ConanFileMock(shared=False)
        conan_file.settings = settings
        cmake = CMake(conan_file)

        self.assertEquals(cmake.definitions["BUILD_SHARED_LIBS"], "OFF")

        conan_file = ConanFileMock(shared=None)
        conan_file.settings = settings
        cmake = CMake(conan_file)

        self.assertNotIn("BUILD_SHARED_LIBS", cmake.definitions)

    def test_verbose(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"

        conan_file = ConanFileMock()
        conan_file.settings = settings
        cmake = CMake(conan_file)

        self.assertNotIn("CMAKE_VERBOSE_MAKEFILE", cmake.definitions)

        cmake.verbose = True
        self.assertEquals(cmake.definitions["CMAKE_VERBOSE_MAKEFILE"], "ON")

        cmake.verbose = False
        self.assertEquals(cmake.definitions["CMAKE_VERBOSE_MAKEFILE"], "OFF")

        cmake.definitions["CMAKE_VERBOSE_MAKEFILE"] = True
        self.assertTrue(cmake.verbose)

        cmake.definitions["CMAKE_VERBOSE_MAKEFILE"] = False
        self.assertFalse(cmake.verbose)

        del cmake.definitions["CMAKE_VERBOSE_MAKEFILE"]
        self.assertFalse(cmake.verbose)

    def set_toolset_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.compiler.toolset = "v140"  # Will be overwritten by parameter

        conan_file = ConanFileMock()
        conan_file.settings = settings

        cmake = CMake(conan_file, toolset="v141")
        self.assertIn('-T "v141"', cmake.command_line)

        # DEPRECATED VARIABLE, NOT MODIFY ANYMORE THE TOOLSET
        with tools.environment_append({"CONAN_CMAKE_TOOLSET": "v141"}):
            cmake = CMake(conan_file)
            self.assertNotIn('-T "v141"', cmake.command_line)

        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "15"
        settings.arch = "x86"
        settings.compiler.toolset = "v140"

        conan_file = ConanFileMock()
        conan_file.settings = settings

        cmake = CMake(conan_file)
        self.assertIn('-T "v140"', cmake.command_line)

    def test_missing_settings(self):
        def instance_with_os_build(os_build):
            settings = Settings.loads(default_settings_yml)
            settings.os_build = os_build
            conan_file = ConanFileMock()
            conan_file.settings = settings
            return CMake(conan_file)

        cmake = instance_with_os_build("Linux")
        self.assertEquals(cmake.generator, "Unix Makefiles")

        cmake = instance_with_os_build("Macos")
        self.assertEquals(cmake.generator, "Unix Makefiles")

        cmake = instance_with_os_build("Windows")
        self.assertEquals(cmake.generator, None)

        with tools.environment_append({"CONAN_CMAKE_GENERATOR": "MyCoolGenerator"}):
            cmake = instance_with_os_build("Windows")
            self.assertEquals(cmake.generator, "MyCoolGenerator")

    def test_cmake_system_version_android(self):
        with tools.environment_append({"CONAN_CMAKE_SYSTEM_NAME": "SomeSystem",
                                       "CONAN_CMAKE_GENERATOR": "SomeGenerator"}):
            settings = Settings.loads(default_settings_yml)
            settings.os = "WindowsStore"
            settings.os.version = "8.1"

            conan_file = ConanFileMock()
            conan_file.settings = settings
            cmake = CMake(conan_file)
            self.assertEquals(cmake.definitions["CMAKE_SYSTEM_VERSION"], "8.1")

            settings = Settings.loads(default_settings_yml)
            settings.os = "Android"
            settings.os.api_level = "32"

            conan_file = ConanFileMock()
            conan_file.settings = settings
            cmake = CMake(conan_file)
            self.assertEquals(cmake.definitions["CMAKE_SYSTEM_VERSION"], "32")

    def install_definitions_test(self):
        conanfile = ConanFileMock()
        conanfile.package_folder = None
        conanfile.settings = Settings.loads(default_settings_yml)
        install_defintions = {"CMAKE_INSTALL_PREFIX": conanfile.package_folder,
                              "CMAKE_INSTALL_BINDIR": "bin",
                              "CMAKE_INSTALL_SBINDIR": "bin",
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
        conanfile.package_folder = "my_package_folder"
        install_defintions["CMAKE_INSTALL_PREFIX"] = conanfile.package_folder
        cmake = CMake(conanfile)
        for key, value in install_defintions.items():
            self.assertEquals(cmake.definitions[key], value)

    @mock.patch('platform.system', return_value="Macos")
    def test_cmake_system_version_osx(self, _):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Macos"

        # No version defined
        conanfile = ConanFileMock()
        conanfile.settings = settings
        cmake = CMake(conanfile)
        self.assertFalse("CMAKE_OSX_DEPLOYMENT_TARGET" in cmake.definitions)
        self.assertFalse("CMAKE_SYSTEM_NAME" in cmake.definitions)
        self.assertFalse("CMAKE_SYSTEM_VERSION" in cmake.definitions)

        # Version defined using Conan env variable
        with tools.environment_append({"CONAN_CMAKE_SYSTEM_VERSION": "23"}):
            conanfile = ConanFileMock()
            conanfile.settings = settings
            cmake = CMake(conanfile)
            self.assertEqual(cmake.definitions["CMAKE_SYSTEM_VERSION"], "23")
            self.assertEqual(cmake.definitions["CMAKE_OSX_DEPLOYMENT_TARGET"], "23")

        # Version defined in settings
        settings.os.version = "10.9"
        conanfile = ConanFileMock()
        conanfile.settings = settings
        cmake = CMake(conanfile)
        self.assertEqual(cmake.definitions["CMAKE_SYSTEM_VERSION"], "10.9")
        self.assertEqual(cmake.definitions["CMAKE_OSX_DEPLOYMENT_TARGET"], "10.9")

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


class ConanFileMock(ConanFile):
    def __init__(self, shared=None, options=None, options_values=None):
        options = options or ""
        self.command = None
        self.path = None
        self.source_folder = self.build_folder = "."
        self.settings = None
        self.options = Options(PackageOptions.loads(options))
        if options_values:
            for var, value in options_values.items():
                self.options._data[var] = value
        self.deps_cpp_info = namedtuple("deps_cpp_info", "sysroot")("/path/to/sysroot")
        self.output = TestBufferConanOutput()
        self.in_local_cache = False
        self.install_folder = "myinstallfolder"
        if shared is not None:
            self.options = namedtuple("options", "shared")(shared)
        self.should_configure = True
        self.should_build = True
        self.should_install = True
        self.should_test = True
        self.generators = []
        self.captured_env = {}

    def run(self, command):
        self.command = command
        self.path = os.environ["PATH"]
        self.captured_env = {key: value for key, value in os.environ.items()}
