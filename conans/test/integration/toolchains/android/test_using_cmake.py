import shutil
import textwrap
import unittest

from conans.test.utils.tools import TestClient
from ._utils import create_library


class SystemToolsTestCase(unittest.TestCase):
    # This test assumes that 'CMake' and 'AndroidNDK' are installed in the system
    #
    # Guidelines: https://developer.android.com/ndk/guides/cmake#command-line

    @classmethod
    def setUpClass(cls):
        if not shutil.which('cmake'):
            raise unittest.SkipTest("CMake expected in PATH")
        if not shutil.which('cmake'):
            raise unittest.SkipTest("CMake expected in PATH")

    def setUp(self):
        current_folder = '/private/var/folders/fc/6mvcrc952dqcjfhl4c7c11ph0000gn/T/tmp4xr45tt5conans/path with spaces'
        self.t = TestClient(current_folder=current_folder)
        create_library(self.t)
        self.t.save({
            'conanfile.py': textwrap.dedent("""
                from conans import ConanFile, CMake, CMakeToolchain

                class Library(ConanFile):
                    name = 'library'
                    settings = 'os', 'arch', 'compiler', 'build_type'
                    exports_sources = "CMakeLists.txt", "lib.h", "lib.cpp"

                    def toolchain(self):
                        tc = CMakeToolchain(self)
                        tc.write_toolchain_files()

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
                os.api_level=16
                arch=x86_64
                compiler=clang
                compiler.version=9
            """)
        })

    def test_regular_build(self):
        # TODO: Remove this test, useless besides validating this project
        self.t.run('create . library/version@')

    def test_use_cmake_toolchain(self):
        """ This is the naïve approach, we follow instruction from CMake in its documentation
            https://cmake.org/cmake/help/latest/manual/cmake-toolchains.7.html#cross-compiling-for-android
            It can be integrated into
        """
        self.t.run('install . library/version@ --profile:host=profile_host --profile:build=default')
        print(self.t.out)
        print()
        self.t.run('create . library/version@ --profile:host=profile_host --profile:build=default')
        print(self.t.out)
        self.fail("AAA")

    def test_use_android_ndk_toolchain(self):
        """ Use the CMake toolchain provided by Android NDK itself """
        pass

