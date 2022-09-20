import platform
import textwrap
import unittest

import pytest

from conan.tools.cmake import CMakeToolchain
from conans.test.utils.tools import TestClient
from ._utils import create_library


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires XCode")
class ToolchainiOSTestCase(unittest.TestCase):

    def setUp(self):
        self.t = TestClient()
        create_library(self.t)
        self._conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.cmake import CMake, CMakeToolchain

            class Library(ConanFile):
                name = 'hello'
                version = '1.0'
                settings = 'os', 'arch', 'compiler', 'build_type'
                exports_sources = 'hello.h', 'hello.cpp', 'CMakeLists.txt'
                options = {{'shared': [True, False]}}
                default_options = {{'shared': False}}

                def generate(self):
                    tc = CMakeToolchain(self, generator={generator})
                    tc.generate()

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
                    self.run("lipo -info Release-iphoneos/libhello.a")

                def package(self):
                    cmake = CMake(self)
                    cmake.install()
            """)

        self.t.save({
            'ios_profile': textwrap.dedent("""
                [settings]
                os=iOS
                os.sdk=iphoneos
                os.version=12.0
                arch=armv8
                compiler=apple-clang
                compiler.version=12.0
                compiler.libcxx=libc++
                build_type=Release
            """)
        })

    @pytest.mark.tool_cmake(version="3.19")
    def test_xcode_generator(self):
        """ Simplest approach:
            https://cmake.org/cmake/help/latest/manual/cmake-toolchains.7.html#cross-compiling-for-ios-tvos-or-watchos
        """
        self.t.save({'conanfile.py': self._conanfile.format(generator='"Xcode"')})

        # Build in the cache
        self.t.run('create . --profile:build=default --profile:host=ios_profile')
        self.assertIn("Non-fat file: Release-iphoneos/libhello.a is architecture: arm64", self.t.out)

        # Build locally
        self.t.run('install . --profile:host=ios_profile --profile:build=default')
        self.t.run_command('cmake . -G"Xcode" -DCMAKE_TOOLCHAIN_FILE={}'.format(CMakeToolchain.filename))
        self.t.run_command('cmake --build . --config Release')
        self.t.run_command("lipo -info Release-iphoneos/libhello.a")
        self.assertIn("Non-fat file: Release-iphoneos/libhello.a is architecture: arm64", self.t.out)

    def test_unix_makefiles_generator(self):
        pass
