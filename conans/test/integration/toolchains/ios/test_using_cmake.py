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
                exports_sources = 'hello.h', 'hello.cpp', 'cpp-wrapper.h', 'cpp-wrapper.mm', 'CMakeLists.txt'
                options = {{'shared': [True, False]}}
                default_options = {{'shared': False}}

                def toolchain(self):
                    tc = CMakeToolchain(self)
                    tc.write_toolchain_files()

                def build(self):
                    cmake = CMake(self, generator={generator})
                    cmake.configure()
                    cmake.build()
                    self.run("lipo -info Release-iphonesimulator/libhello.a")

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.dylib*", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.libs = ["hello"]
            """)

        self.t.save({
            'ios_profile': textwrap.dedent("""
                [settings]
                os=iOS
                os.version=12.0
                arch=x86_64
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
        self.assertIn("Non-fat file: Release-iphonesimulator/libhello.a is architecture: arm64",
                      self.t.out)

        # Build locally
        self.t.run('install . --profile:host=ios_profile --profile:build=default')
        self.t.run_command('cmake . -DCMAKE_TOOLCHAIN_FILE={}'.format(CMakeToolchainBase.filename))
        self.t.run_command('cmake --build . --config Release')

    def test_unix_makefiles_generator(self):
        pass
