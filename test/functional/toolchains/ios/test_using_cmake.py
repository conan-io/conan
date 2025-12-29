import platform
import textwrap

import pytest

from conan.tools.cmake import CMakeToolchain
from conan.test.utils.tools import TestClient
from ._utils import create_library


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires XCode")
@pytest.mark.tool("cmake", "3.19")
def test_xcode_ios_generator():
    """ Simplest approach:
        https://cmake.org/cmake/help/latest/manual/cmake-toolchains.7.html#cross-compiling-for-ios-tvos-or-watchos
    """
    t = TestClient()
    create_library(t)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain

        class Library(ConanFile):
            name = 'hello'
            version = '1.0'
            settings = 'os', 'arch', 'compiler', 'build_type'
            exports_sources = 'hello.h', 'hello.cpp', 'CMakeLists.txt'
            options = {'shared': [True, False]}
            default_options = {'shared': False}

            def generate(self):
                tc = CMakeToolchain(self, generator="Xcode")
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

    ios_profile = textwrap.dedent("""
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

    t.save({'conanfile.py': conanfile,
            "ios_profile": ios_profile})

    # Build in the cache
    t.run('create . --profile:build=default --profile:host=ios_profile')
    assert "Non-fat file: Release-iphoneos/libhello.a is architecture: arm64" in t.out

    # Build locally
    t.run('install . --profile:host=ios_profile --profile:build=default')
    t.run_command('cmake . -G"Xcode" -DCMAKE_TOOLCHAIN_FILE={}'.format(CMakeToolchain.filename))
    t.run_command('cmake --build . --config Release')
    t.run_command("lipo -info Release-iphoneos/libhello.a")
    assert "Non-fat file: Release-iphoneos/libhello.a is architecture: arm64" in t.out
