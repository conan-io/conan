import os
import shutil
import sys
import tempfile
import unittest
from collections import namedtuple

from conans import tools
from conans.model.conan_file import ConanFile
from conans.model.settings import Settings
from conans.client.conf import default_settings_yml
from conans.client.cmake import CMake
from conans.tools import cpu_count

import platform

from conans.util.files import save


class CMakeTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def loads_default_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"
        conan_file = ConanFileMock()
        conan_file.settings = settings

        def check(text, build_config, generator=None):
            os = str(settings.os)
            for cmake_system_name in (True, False):
                cross = ("-DCMAKE_SYSTEM_NAME=\"%s\" -DCMAKE_SYSROOT=\"/path/to/sysroot\" " % {"Macos": "Darwin"}.get(os, os)
                         if (platform.system() != os and cmake_system_name) else "")
                cmake = CMake(conan_file, generator=generator, cmake_system_name=cmake_system_name)
                new_text = text.replace("-DCONAN_EXPORTED", "%s-DCONAN_EXPORTED" % cross)
                if "Visual Studio" in text:
                    cores = ('-DCONAN_CXX_FLAGS="/MP{0}" '
                             '-DCONAN_C_FLAGS="/MP{0}" '.format(tools.cpu_count()))
                    new_text = new_text.replace("-Wno-dev", "%s-Wno-dev" % cores)
                self.assertEqual(new_text, cmake.command_line)
                self.assertEqual(build_config, cmake.build_config)

        check('-G "Visual Studio 12 2013" -DCONAN_EXPORTED="1" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" -Wno-dev',
              "")

        check('-G "Custom Generator" -DCONAN_EXPORTED="1" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" -Wno-dev',
              '', generator="Custom Generator")

        settings.build_type = "Debug"
        check('-G "Visual Studio 12 2013" -DCONAN_EXPORTED="1" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" -Wno-dev',
              '--config Debug')

        settings.arch = "x86_64"
        check('-G "Visual Studio 12 2013 Win64" -DCONAN_EXPORTED="1" '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" -Wno-dev',
              '--config Debug')

        settings.compiler = "gcc"
        settings.compiler.version = "4.8"
        check('-G "MinGW Makefiles" -DCMAKE_BUILD_TYPE="Debug" -DCONAN_EXPORTED="1" '
              '-DCONAN_COMPILER="gcc" -DCONAN_COMPILER_VERSION="4.8" -Wno-dev',
              "")

        settings.os = "Linux"
        settings.arch = "x86"
        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE="Debug"'
              ' -DCONAN_EXPORTED="1" -DCONAN_COMPILER="gcc" '
              '-DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS="-m32" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m32" -DCONAN_C_FLAGS="-m32" -Wno-dev',
              "")

        settings.arch = "x86_64"
        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE="Debug"'
              ' -DCONAN_EXPORTED="1" -DCONAN_COMPILER="gcc" '
              '-DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" -Wno-dev',
              "")

        settings.os = "FreeBSD"
        settings.compiler = "clang"
        settings.compiler.version = "3.8"
        settings.arch = "x86"
        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE="Debug"'
              ' -DCONAN_EXPORTED="1" -DCONAN_COMPILER="clang" '
              '-DCONAN_COMPILER_VERSION="3.8" -DCONAN_CXX_FLAGS="-m32" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m32" -DCONAN_C_FLAGS="-m32" -Wno-dev',
              "")

        settings.arch = "x86_64"
        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE="Debug"'
              ' -DCONAN_EXPORTED="1" -DCONAN_COMPILER="clang" '
              '-DCONAN_COMPILER_VERSION="3.8" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" -Wno-dev',
              "")

        settings.os = "SunOS"
        settings.compiler = "sun-cc"
        settings.compiler.version = "5.10"
        settings.arch = "x86"
        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE="Debug"'
              ' -DCONAN_EXPORTED="1" -DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS="-m32" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m32" -DCONAN_C_FLAGS="-m32" -Wno-dev',
              "")

        settings.arch = "x86_64"
        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE="Debug"'
              ' -DCONAN_EXPORTED="1" -DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" -Wno-dev',
              "")

        settings.arch = "sparc"

        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE="Debug" -DCONAN_EXPORTED="1" '
              '-DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS="-m32" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m32" -DCONAN_C_FLAGS="-m32" -Wno-dev',
              "")

        settings.arch = "sparcv9"
        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE="Debug" -DCONAN_EXPORTED="1" '
              '-DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS="-m64" '
              '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" -Wno-dev',
              "")

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
        cross = "-DCMAKE_SYSTEM_NAME=\"Linux\" -DCMAKE_SYSROOT=\"/path/to/sysroot\" " if platform.system() != "Linux" else ""
        self.assertEqual('-G "Unix Makefiles" %s-DCONAN_EXPORTED="1" -DCONAN_COMPILER="gcc" '
                         '-DCONAN_COMPILER_VERSION="4.9" -DCONAN_CXX_FLAGS="-m64" '
                         '-DCONAN_SHARED_LINKER_FLAGS="-m64" -DCONAN_C_FLAGS="-m64" -Wno-dev' % cross,
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
        self.assertNotIn("-DCMAKE_SYSROOT=", cmake.flags) if platform.system() == "Windows" else ""

        # Now activate cross build and check sysroot
        with(tools.environment_append({"CONAN_CMAKE_SYSTEM_NAME": "Android"})):
            cmake = CMake(conan_file)
            self.assertEquals(cmake.definitions["CMAKE_SYSROOT"], "/path/to/sysroot")

    def test_deprecated_behaviour(self):
        """"Remove when deprecate the old settings parameter to CMake and conanfile to configure/build/test"""
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"
        settings.os = "Windows"

        dot_dir = "." if sys.platform == 'win32' else "'.'"

        cross = "-DCMAKE_SYSTEM_NAME=\"Windows\" " if platform.system() != "Windows" else ""

        conan_file = ConanFileMock()
        conan_file.settings = settings
        cmake = CMake(settings)
        cmake.configure(conan_file)
        cores = '-DCONAN_CXX_FLAGS="/MP{0}" -DCONAN_C_FLAGS="/MP{0}" '.format(tools.cpu_count())
        self.assertEqual('cd {0} && cmake -G "Visual Studio 12 2013" {1}-DCONAN_EXPORTED="1" '
                         '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" {2}'
                         '-Wno-dev {0}'.format(dot_dir, cross, cores),
                         conan_file.command)

        cmake.build(conan_file)
        self.assertEqual('cmake --build %s' % dot_dir, conan_file.command)
        cmake.test()
        self.assertEqual('cmake --build %s %s' % (dot_dir, CMakeTest.scape('--target RUN_TESTS')), conan_file.command)

    def convenient_functions_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.compiler.runtime = "MDd"
        settings.arch = "x86"
        settings.build_type = None

        if sys.platform == 'win32':
            dot_dir = "."
            tempdir = self.tempdir
        else:
            dot_dir = "'.'"
            tempdir = "'" + self.tempdir + "'"

        conan_file = ConanFileMock()
        conan_file.settings = settings
        cmake = CMake(conan_file)

        cross = "-DCMAKE_SYSTEM_NAME=\"Windows\" -DCMAKE_SYSROOT=\"/path/to/sysroot\" " if platform.system() != "Windows" else ""
        target_test = CMakeTest.scape('--target RUN_TESTS')

        cmake.configure()

        cores = '-DCONAN_CXX_FLAGS="/MP{0}" -DCONAN_C_FLAGS="/MP{0}" '.format(tools.cpu_count())
        self.assertEqual('cd {0} && cmake -G "Visual Studio 12 2013" -DCONAN_LINK_RUNTIME="/MDd" {1}-DCONAN_EXPORTED="1"'
                         ' -DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" {2}'
                         '-Wno-dev {0}'.format(dot_dir, cross, cores),
                         conan_file.command)

        cmake.build()
        self.assertEqual('cmake --build %s' % dot_dir, conan_file.command)

        cmake.test()
        self.assertEqual('cmake --build %s %s' % (dot_dir, target_test), conan_file.command)

        settings.build_type = "Debug"
        cmake = CMake(conan_file)
        cmake.build()
        self.assertEqual('cmake --build %s --config Debug' % dot_dir, conan_file.command)

        cmake.test()
        self.assertEqual('cmake --build %s --config Debug %s' % (dot_dir, target_test), conan_file.command)

        cmake.configure(source_dir="/source", build_dir=self.tempdir,
                        args=['--foo "bar"'], defs={"SHARED": True})
        if sys.platform == 'win32':
            escaped_args = r'"--foo \"bar\"" -DSHARED="True" /source'
        else:
            escaped_args = "'--foo \"bar\"' -DSHARED=\"True\" '/source'"

        self.assertEqual('cd %s && cmake -G "Visual Studio 12 2013" -DCONAN_LINK_RUNTIME="/MDd" %s-DCONAN_EXPORTED="1" '
                         '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" %s'
                         '-Wno-dev %s' % (tempdir, cross, cores, escaped_args),
                         conan_file.command)

        cmake.build(args=["--bar 'foo'"], target="install")
        if sys.platform == 'win32':
            escaped_args = '--target install "--bar \'foo\'"'
        else:
            escaped_args = r"'--target' 'install' '--bar '\''foo'\'''"
        self.assertEqual('cmake --build %s --config Debug %s' % (tempdir, escaped_args),
                         conan_file.command)

        cmake.test(args=["--bar 'foo'"])
        if sys.platform == 'win32':
            escaped_args = '%s "--bar \'foo\'"' % target_test
        else:
            escaped_args = r"%s '--bar '\''foo'\'''" % target_test
        self.assertEqual('cmake --build %s --config Debug %s' % (tempdir, escaped_args),
                         conan_file.command)

        settings.build_type = "Release"
        cmake = CMake(conan_file)
        cmake.build()
        self.assertEqual('cmake --build %s --config Release' % dot_dir, conan_file.command)

        cmake.test()
        self.assertEqual('cmake --build %s --config Release %s' % (dot_dir, target_test), conan_file.command)

        cmake.build(build_dir=self.tempdir)
        self.assertEqual('cmake --build %s --config Release' % tempdir, conan_file.command)

        cmake.test(build_dir=self.tempdir)
        self.assertEqual('cmake --build %s --config Release %s' % (tempdir, target_test), conan_file.command)

        settings.compiler = "gcc"
        settings.compiler.version = "5.4"
        cmake = CMake(conan_file)
        cmake.build()
        self.assertEqual('cmake --build %s' % (CMakeTest.scape('. -- -j%i' % cpu_count())), conan_file.command)

        cmake.test()
        self.assertEqual('cmake --build %s' % (CMakeTest.scape('. --target test -- -j%i' % cpu_count())), conan_file.command)

        cmake.build(args=['foo', '--', 'bar'])
        self.assertEqual('cmake --build %s' % (CMakeTest.scape('. foo -- bar -j%i' % cpu_count())), conan_file.command)

        cmake.test(args=['foo', '--', 'bar'])
        self.assertEqual('cmake --build %s' % (CMakeTest.scape('. --target test foo -- bar -j%i' % cpu_count())), conan_file.command)

        cmake = CMake(conan_file, parallel=False)
        cmake.build()
        self.assertEqual('cmake --build %s' % CMakeTest.scape('.'), conan_file.command)

        cmake.test()
        self.assertEqual('cmake --build %s' % CMakeTest.scape('. --target test'), conan_file.command)

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

    @staticmethod
    def scape(args):
        pattern = "%s" if sys.platform == "win32" else r"'%s'"
        return ' '.join(pattern % i for i in args.split())


class ConanFileMock(ConanFile):
    def __init__(self, shared=None):
        self.command = None
        self.path = None
        self._conanfile_directory = "."
        self.source_folder = self.build_folder = "."
        self.settings = None
        self.deps_cpp_info = namedtuple("deps_cpp_info", "sysroot")("/path/to/sysroot")
        self.output = namedtuple("output", "warn")(lambda x: x)
        if shared is not None:
            self.options = namedtuple("options", "shared")(shared)

    def run(self, command):
        self.command = command
        self.path = os.environ["PATH"]
