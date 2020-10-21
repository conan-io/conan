import platform
import textwrap
import unittest

from conans.client.toolchain.cmake.base import CMakeToolchainBase
from conans.test.utils.tools import TestClient
from ._utils import create_library


@unittest.skipUnless(platform.system() == "Darwin", "Requires XCode")
class ToolchainiOSTestCase(unittest.TestCase):

    def setUp(self):
        self.t = TestClient()
        create_library(self.t)
        self._conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake, CMakeToolchain


            class Library(ConanFile):
                name = 'hello'
                version = '1.0'
                settings = 'os', 'arch', 'compiler', 'build_type'
                exports_sources = 'hello.h', 'hello.cpp', 'CMakeLists.txt'
                options = {{'shared': [True, False]}}
                default_options = {{'shared': False}}
                _cmake = None

                def _configure_cmake(self):
                    if not self._cmake:
                        self._cmake = CMake(self, generator={generator}, parallel=False)
                        self._cmake.configure()
                    return self._cmake

                def toolchain(self):
                    tc = CMakeToolchain(self)
                    tc.write_toolchain_files()

                def build(self):
                    cmake = self._configure_cmake()
                    cmake.configure()
                    cmake.build()
                    self.run("lipo -info Release-iphoneos/libhello.a")

                def package(self):
                    cmake = self._configure_cmake()
                    cmake.install()
            """)

        self.t.save({
            'ios_profile': textwrap.dedent("""
                [settings]
                os=iOS
                os.version=12.0
                arch=armv8
                compiler=apple-clang
                compiler.version=12.0
                compiler.libcxx=libc++
                build_type=Release
            """)
        })

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
        self.t.run_command('cmake . -G"Xcode" -DCMAKE_TOOLCHAIN_FILE={}'.format(CMakeToolchainBase.filename))
        self.t.run_command('cmake --build . --config Release')
        self.t.run_command("lipo -info Release-iphoneos/libhello.a")
        self.assertIn("Non-fat file: Release-iphoneos/libhello.a is architecture: arm64", self.t.out)

    def test_unix_makefiles_generator(self):
        pass
