import unittest
from conans.model.settings import Settings
from conans.client.conf import default_settings_yml
from conans.client.cmake import CMake


class CMakeTest(unittest.TestCase):

    def loads_default_test(self):
        settings = Settings.loads(default_settings_yml)
        settings.compiler = "Visual Studio"
        settings.compiler.version = "12"
        settings.arch = "x86"

        cmake = CMake(settings)
        self.assertEqual('-G "Visual Studio 12"   -DCONAN_COMPILER="Visual Studio" '
                         '-DCONAN_COMPILER_VERSION="12" -Wno-dev', cmake.command_line)
        self.assertEqual('', cmake.build_config)
        settings.build_type = "Debug"
        self.assertEqual('-G "Visual Studio 12"   -DCONAN_COMPILER="Visual Studio" '
                         '-DCONAN_COMPILER_VERSION="12" -Wno-dev', cmake.command_line)
        self.assertEqual('--config Debug', cmake.build_config)

        settings.arch = "x86_64"
        self.assertEqual('-G "Visual Studio 12 Win64"   -DCONAN_COMPILER="Visual Studio" '
                         '-DCONAN_COMPILER_VERSION="12" -Wno-dev', cmake.command_line)

        settings.os = "Windows"
        settings.compiler = "gcc"
        settings.compiler.version = "4.8"
        self.assertEqual('-G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Debug  -DCONAN_COMPILER="gcc" '
                         '-DCONAN_COMPILER_VERSION="4.8" -Wno-dev', cmake.command_line)

        settings.os = "Linux"
        settings.arch = "x86"
        self.assertEqual('-G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Debug  -DCONAN_COMPILER="gcc" '
                         '-DCONAN_COMPILER_VERSION="4.8" -DCONAN_CXX_FLAGS=-m32 '
                         '-DCONAN_SHARED_LINKER_FLAGS=-m32 -DCONAN_C_FLAGS=-m32 -Wno-dev',
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
        self.assertEqual('-G "Unix Makefiles"   -DCONAN_COMPILER="gcc" '
                         '-DCONAN_COMPILER_VERSION="4.9" -Wno-dev', cmake.command_line)
