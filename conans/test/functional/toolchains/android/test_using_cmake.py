import os
import platform
import textwrap

import pytest

from conan.tools.cmake import CMakeToolchain
from conans.test.functional.toolchains.android._utils import create_library
from conans.test.utils.tools import TestClient


@pytest.fixture
def client():
    t = TestClient()
    create_library(t)
    t.save({
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
                    cmake.build()

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
            [conf]
            tools.android:ndk_path={ndk_path}
        """.format(ndk_path=os.getenv("TEST_CONAN_ANDROID_NDK")))
    })
    return t


@pytest.mark.tool_cmake
@pytest.mark.tool_android_ndk
@pytest.mark.skipif(platform.system() != "Darwin", reason="NDK only installed on MAC")
def test_use_cmake_toolchain(client):
    """ This is the naive approach, we follow instruction from CMake in its documentation
        https://cmake.org/cmake/help/latest/manual/cmake-toolchains.7.html#cross-compiling-for-android
    """
    # Build in the cache
    client.run('create . library/version@ --profile:host=profile_host --profile:build=default')

    # Build locally
    client.run('install . library/version@ --profile:host=profile_host --profile:build=default')
    client.run_command('cmake . -DCMAKE_TOOLCHAIN_FILE={}'.format(CMakeToolchain.filename))
    client.run_command('cmake --build .')
