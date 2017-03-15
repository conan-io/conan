import os
import shutil
import sys
import tempfile
import unittest
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

        def check(text, build_config, generator=None):
            os = str(settings.os)
            for cmake_system_name in (True, False):
                cross = ("-DCMAKE_SYSTEM_NAME=%s " % {"Macos": "Darwin"}.get(os, os)
                         if (platform.system() != os and cmake_system_name) else "")
                cmake = CMake(settings, generator=generator, cmake_system_name=cmake_system_name)
                new_text = text.replace("-DCONAN_EXPORTED", "%s-DCONAN_EXPORTED" % cross)
                self.assertEqual(new_text, cmake.command_line)
                self.assertEqual(build_config, cmake.build_config)

        check('-G "Visual Studio 12 2013" -DCONAN_EXPORTED=1 '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" -Wno-dev',
              "")

        check('-G "Custom Generator" -DCONAN_EXPORTED=1 '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" -Wno-dev',
              '', generator="Custom Generator")

        settings.build_type = "Debug"
        check('-G "Visual Studio 12 2013" -DCONAN_EXPORTED=1 '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" -Wno-dev',
              '--config Debug')

        settings.arch = "x86_64"
        check('-G "Visual Studio 12 2013 Win64" -DCONAN_EXPORTED=1 '
              '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" -Wno-dev',
              '--config Debug')

        settings.compiler = "gcc"
        settings.compiler.version = "4.8"
        check('-G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Debug -DCONAN_EXPORTED=1 '
              '-DCONAN_COMPILER="gcc" -DCONAN_COMPILER_VERSION="4.8" -Wno-dev',
              "")

        settings.os = "Linux"
        settings.arch = "x86"
        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug'
              ' -DCONAN_EXPORTED=1 -DCONAN_COMPILER="gcc" '
              '-DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS=-m32 '
              '-DCONAN_SHARED_LINKER_FLAGS=-m32 -DCONAN_C_FLAGS=-m32 -Wno-dev',
              "")

        settings.arch = "x86_64"
        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug'
              ' -DCONAN_EXPORTED=1 -DCONAN_COMPILER="gcc" '
              '-DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS=-m64 '
              '-DCONAN_SHARED_LINKER_FLAGS=-m64 -DCONAN_C_FLAGS=-m64 -Wno-dev',
              "")

        settings.os = "FreeBSD"
        settings.compiler = "clang"
        settings.compiler.version = "3.8"
        settings.arch = "x86"
        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug'
              ' -DCONAN_EXPORTED=1 -DCONAN_COMPILER="clang" '
              '-DCONAN_COMPILER_VERSION="3.8" -DCONAN_CXX_FLAGS=-m32 '
              '-DCONAN_SHARED_LINKER_FLAGS=-m32 -DCONAN_C_FLAGS=-m32 -Wno-dev',
              "")

        settings.arch = "x86_64"
        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug'
              ' -DCONAN_EXPORTED=1 -DCONAN_COMPILER="clang" '
              '-DCONAN_COMPILER_VERSION="3.8" -DCONAN_CXX_FLAGS=-m64 '
              '-DCONAN_SHARED_LINKER_FLAGS=-m64 -DCONAN_C_FLAGS=-m64 -Wno-dev',
              "")

        settings.os = "SunOS"
        settings.compiler = "sun-cc"
        settings.compiler.version = "5.10"
        settings.arch = "x86"
        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug'
              ' -DCONAN_EXPORTED=1 -DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS=-m32 '
              '-DCONAN_SHARED_LINKER_FLAGS=-m32 -DCONAN_C_FLAGS=-m32 -Wno-dev',
              "")

        settings.arch = "x86_64"
        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug'
              ' -DCONAN_EXPORTED=1 -DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS=-m64 '
              '-DCONAN_SHARED_LINKER_FLAGS=-m64 -DCONAN_C_FLAGS=-m64 -Wno-dev',
              "")

        settings.arch = "sparc"

        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug -DCONAN_EXPORTED=1 '
              '-DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS=-m32 '
              '-DCONAN_SHARED_LINKER_FLAGS=-m32 -DCONAN_C_FLAGS=-m32 -Wno-dev',
              "")

        settings.arch = "sparcv9"
        check('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug -DCONAN_EXPORTED=1 '
              '-DCONAN_COMPILER="sun-cc" '
              '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS=-m64 '
              '-DCONAN_SHARED_LINKER_FLAGS=-m64 -DCONAN_C_FLAGS=-m64 -Wno-dev',
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

        cmake = CMake(settings)
        cross = "-DCMAKE_SYSTEM_NAME=Linux " if platform.system() != "Linux" else ""
        self.assertEqual('-G "Unix Makefiles" %s-DCONAN_EXPORTED=1 -DCONAN_COMPILER="gcc" '
                         '-DCONAN_COMPILER_VERSION="4.9" -DCONAN_CXX_FLAGS=-m64 '
                         '-DCONAN_SHARED_LINKER_FLAGS=-m64 -DCONAN_C_FLAGS=-m64 -Wno-dev' % cross,
                         cmake.command_line)

    def convenient_functions_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"
        settings.os = "Windows"

        if sys.platform == 'win32':
            dot_dir = "."
            tempdir = self.tempdir
        else:
            dot_dir = "'.'"
            tempdir = "'" + self.tempdir + "'"

        cmake = CMake(settings)
        conan_file = ConanFileMock()

        cross = "-DCMAKE_SYSTEM_NAME=Windows " if platform.system() != "Windows" else ""

        cmake.configure(conan_file)
        self.assertEqual('cd {0} && cmake -G "Visual Studio 12 2013" {1}-DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
                         '-Wno-dev {0}'.format(dot_dir, cross),
                         conan_file.command)

        cmake.build(conan_file)
        self.assertEqual('cmake --build %s' % dot_dir, conan_file.command)

        settings.build_type = "Debug"
        cmake.build(conan_file)
        self.assertEqual('cmake --build %s --config Debug' % dot_dir, conan_file.command)

        cmake.configure(conan_file, source_dir="/source", build_dir=self.tempdir,
                        args=['--foo "bar"'], defs={"SHARED": True})
        if sys.platform == 'win32':
            escaped_args = r'"--foo \"bar\"" -DSHARED=True /source'
        else:
            escaped_args = "'--foo \"bar\"' '-DSHARED=True' '/source'"
        self.assertEqual('cd %s && cmake -G "Visual Studio 12 2013" %s-DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
                         '-Wno-dev %s' % (tempdir, cross, escaped_args),
                         conan_file.command)

        cmake.build(conan_file, args=["--bar 'foo'"], target="install")
        if sys.platform == 'win32':
            escaped_args = '--target install "--bar \'foo\'"'
        else:
            escaped_args = r"'--target' 'install' '--bar '\''foo'\'''"
        self.assertEqual('cmake --build %s --config Debug %s' % (tempdir, escaped_args),
                         conan_file.command)

        settings.build_type = "Release"
        cmake = CMake(settings)
        cmake.build(conan_file)
        self.assertEqual('cmake --build %s --config Release' % dot_dir, conan_file.command)

        cmake.build(conan_file, build_dir=self.tempdir)
        self.assertEqual('cmake --build %s --config Release' % tempdir, conan_file.command)

        settings.compiler = "gcc"
        settings.compiler.version = "5.4"
        cmake = CMake(settings)
        cmake.build(conan_file)
        if sys.platform == 'win32':
            self.assertEqual('cmake --build . -- -j%i' % cpu_count(), conan_file.command)
        else:
            self.assertEqual("cmake --build '.' '--' '-j%i'" % cpu_count(), conan_file.command)

        cmake.build(conan_file, args=['foo', '--', 'bar'])
        if sys.platform == 'win32':
            self.assertEqual('cmake --build . foo -- bar -j%i' % cpu_count(), conan_file.command)
        else:
            self.assertEqual("cmake --build '.' 'foo' '--' 'bar' '-j%i'" % cpu_count(), conan_file.command)

        cmake = CMake(settings, parallel=False)
        cmake.build(conan_file)
        if sys.platform == 'win32':
            self.assertEqual('cmake --build .', conan_file.command)
        else:
            self.assertEqual("cmake --build '.'", conan_file.command)

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

        cmake = CMake(settings)
        cmake.configure(conanfile)
        self.assertIn(self.tempdir, conanfile.path)

        cmake.generator = "MinGW Makefiles"
        cmake.configure(conanfile)
        self.assertNotIn(self.tempdir, conanfile.path)

        # Automatic gcc
        settings = Settings.loads(default_settings_yml)
        settings.os = "Windows"
        settings.compiler = "gcc"
        settings.compiler.version = "5.4"
        settings.arch = "x86"

        cmake = CMake(settings)
        cmake.configure(conanfile)
        self.assertNotIn(self.tempdir, conanfile.path)


class ConanFileMock(object):
    def __init__(self):
        self.command = None
        self.conanfile_directory = "."
        self.path = None

    def run(self, command):
        self.command = command
        self.path = os.environ["PATH"]
