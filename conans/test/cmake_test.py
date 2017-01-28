import shutil
import sys
import tempfile
import unittest
from conans.model.settings import Settings
from conans.client.conf import default_settings_yml
from conans.client.cmake import CMake


class CMakeTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def loads_default_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"

        cmake = CMake(settings)
        self.assertEqual('-G "Visual Studio 12 2013" -DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" -Wno-dev',
                         cmake.command_line)
        self.assertEqual('', cmake.build_config)

        cmake = CMake(settings, generator="Custom Generator")
        self.assertEqual('-G "Custom Generator" -DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" -Wno-dev',
                         cmake.command_line)
        self.assertEqual('', cmake.build_config)

        settings.build_type = "Debug"
        cmake = CMake(settings)
        self.assertEqual('-G "Visual Studio 12 2013" -DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" -Wno-dev',
                         cmake.command_line)
        self.assertEqual('--config Debug', cmake.build_config)

        settings.arch = "x86_64"
        cmake = CMake(settings)
        self.assertEqual('-G "Visual Studio 12 2013 Win64" -DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" -Wno-dev',
                         cmake.command_line)

        settings.os = "Windows"
        settings.compiler = "gcc"
        settings.compiler.version = "4.8"
        cmake = CMake(settings)
        self.assertEqual('-G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Debug -DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="gcc" -DCONAN_COMPILER_VERSION="4.8" -Wno-dev',
                         cmake.command_line)

        settings.os = "Linux"
        settings.arch = "x86"
        cmake = CMake(settings)
        self.assertEqual('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug -DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="gcc" '
                         '-DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS=-m32 '
                         '-DCONAN_SHARED_LINKER_FLAGS=-m32 -DCONAN_C_FLAGS=-m32 -Wno-dev',
                         cmake.command_line)

        settings.arch = "x86_64"
        cmake = CMake(settings)
        self.assertEqual('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug -DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="gcc" '
                         '-DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS=-m64 '
                         '-DCONAN_SHARED_LINKER_FLAGS=-m64 -DCONAN_C_FLAGS=-m64 -Wno-dev',
                         cmake.command_line)

        settings.os = "FreeBSD"
        settings.compiler = "clang"
        settings.compiler.version = "3.8"
        settings.arch = "x86"
        cmake = CMake(settings)
        self.assertEqual('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug -DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="clang" '
                         '-DCONAN_COMPILER_VERSION="3.8" -DCONAN_CXX_FLAGS=-m32 '
                         '-DCONAN_SHARED_LINKER_FLAGS=-m32 -DCONAN_C_FLAGS=-m32 -Wno-dev',
                         cmake.command_line)

        settings.arch = "x86_64"
        cmake = CMake(settings)
        self.assertEqual('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug -DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="clang" '
                         '-DCONAN_COMPILER_VERSION="3.8" -DCONAN_CXX_FLAGS=-m64 '
                         '-DCONAN_SHARED_LINKER_FLAGS=-m64 -DCONAN_C_FLAGS=-m64 -Wno-dev',
                         cmake.command_line)

        settings.os = "SunOS"
        settings.compiler = "sun-cc"
        settings.compiler.version = "5.10"
        settings.arch = "x86"
        cmake = CMake(settings)
        self.assertEqual('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug -DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="sun-cc" '
                         '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS=-m32 '
                         '-DCONAN_SHARED_LINKER_FLAGS=-m32 -DCONAN_C_FLAGS=-m32 -Wno-dev',
                         cmake.command_line)

        settings.arch = "x86_64"
        cmake = CMake(settings)
        self.assertEqual('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug -DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="sun-cc" '
                         '-DCONAN_COMPILER_VERSION="5.10" -DCONAN_CXX_FLAGS=-m64 '
                         '-DCONAN_SHARED_LINKER_FLAGS=-m64 -DCONAN_C_FLAGS=-m64 -Wno-dev',
                         cmake.command_line)

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
        self.assertEqual('-G "Unix Makefiles" -DCONAN_EXPORTED=1 -DCONAN_COMPILER="gcc" '
                         '-DCONAN_COMPILER_VERSION="4.9" -DCONAN_CXX_FLAGS=-m64 '
                         '-DCONAN_SHARED_LINKER_FLAGS=-m64 -DCONAN_C_FLAGS=-m64 -Wno-dev',
                         cmake.command_line)

    def convenient_functions_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"

        if sys.platform == 'win32':
            dot_dir = "."
            tempdir = self.tempdir
        else:
            dot_dir = "'.'"
            tempdir = "'" + self.tempdir + "'"

        cmake = CMake(settings)
        conan_file = ConanFileMock()

        cmake.configure(conan_file)
        self.assertEqual('cd {0} && cmake -G "Visual Studio 12 2013" -DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
                         '-Wno-dev {0}'.format(dot_dir),
                         conan_file.command)

        cmake.build(conan_file)
        self.assertEqual('cmake --build %s' % dot_dir, conan_file.command)

        settings.build_type = "Debug"
        cmake.build(conan_file)
        self.assertEqual('cmake --build %s --config Debug' % dot_dir, conan_file.command)

        cmake.configure(conan_file, source_dir="/source", build_dir=self.tempdir,
                        args=['--foo "bar"'], vars={"SHARED": True})
        if sys.platform == 'win32':
            escaped_args = r'"--foo \"bar\"" -DSHARED=True /source'
        else:
            escaped_args = "'--foo \"bar\"' '-DSHARED=True' '/source'"
        self.assertEqual('cd %s && cmake -G "Visual Studio 12 2013" -DCONAN_EXPORTED=1 '
                         '-DCONAN_COMPILER="Visual Studio" -DCONAN_COMPILER_VERSION="12" '
                         '-Wno-dev %s' % (tempdir, escaped_args),
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


class ConanFileMock(object):
    def __init__(self):
        self.command = None
        self.conanfile_directory = "."

    def run(self, command):
        self.command = command
