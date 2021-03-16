import textwrap
import unittest

from conan.tools.cmake.base import CMakeToolchainBase
from conans.client.tools import which
from conans.test.utils.tools import TestClient
from ._utils import create_library


class AndroidToolchainTestCase(unittest.TestCase):
    # This test assumes that 'CMake' and 'AndroidNDK' are available in the system
    #
    # Guidelines: https://developer.android.com/ndk/guides/cmake#command-line

    @classmethod
    def setUpClass(cls):
        if not which('cmake'):
            raise unittest.SkipTest("CMake expected in PATH")
        if not which('ndk-build'):
            raise unittest.SkipTest("ANDROID_NDK (ndk-build) expected in PATH")

    def setUp(self):
        self.t = TestClient()
        create_library(self.t)
        self.t.save({
            'conanfile.py': textwrap.dedent("""
                from conans import ConanFile
                from conan.tools.cmake import CMake, CMakeToolchain

                class Library(ConanFile):
                    name = 'library'
                    settings = 'os', 'arch', 'compiler', 'build_type'
                    exports_sources = "CMakeLists.txt", "lib.h", "lib.cpp"
                    options = {'shared': [True, False]}
                    default_options = {'shared': False}

                    def generate(self):
                        tc = CMakeToolchain(self)
                        tc.generate()

                    def build(self):
                        cmake = CMake(self)
                        cmake.configure()

                    def package(self):
                        cmake = CMake(self)
                        cmake.install()
                """),
            'profile_host': textwrap.dedent("""
                [settings]
                os=Android
                os.api_level=23
                arch=x86_64
                compiler=clang
                compiler.version=9
                compiler.libcxx=c++_shared
                build_type=Release
            """)
        })

    def test_use_cmake_toolchain(self):
        """ This is the naive approach, we follow instruction from CMake in its documentation
            https://cmake.org/cmake/help/latest/manual/cmake-toolchains.7.html#cross-compiling-for-android
        """
        # Build in the cache
        self.t.run('create . library/version@ --profile:host=profile_host --profile:build=default')

        # Build locally
        self.t.run('install . library/version@ --profile:host=profile_host --profile:build=default')
        self.t.run_command('cmake . -DCMAKE_TOOLCHAIN_FILE={}'.format(CMakeToolchainBase.filename))
        self.t.run_command('cmake --build .')
