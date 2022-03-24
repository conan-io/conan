import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for Apple")
@pytest.mark.tool_cmake
def test_cross_build_test_package():
    # https://github.com/conan-io/conan/issues/9202
    profile_build = textwrap.dedent("""
        [settings]
        os=Macos
        arch=x86_64
        compiler=apple-clang
        compiler.version=13
        compiler.libcxx=libc++
        build_type=Release
        [options]
        [build_requires]
        [env]
    """)

    profile_host = textwrap.dedent("""
        [settings]
        os=iOS
        os.version=13.0
        arch=x86_64
        compiler=apple-clang
        compiler.version=13
        compiler.libcxx=libc++
        build_type=Release
        [options]
        [build_requires]
        [env]
    """)

    test_cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.1)
        project(PackageTest CXX)
        include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
        conan_basic_setup(TARGETS)
        find_package(hello REQUIRED CONFIG)
        add_executable(example example.cpp)
        target_link_libraries(example hello::hello)
        set_property(TARGET example PROPERTY CXX_STANDARD 11)
    """)

    test_conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake, tools
        class HelloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "cmake", "cmake_find_package_multi"
            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
            def test(self):
                if not tools.cross_building(self):
                    os.chdir("bin")
                    self.run(".%sexample" % os.sep)
    """)

    client = TestClient()
    client.run("new hello/0.1 -t")
    client.save({"profile_build": profile_build,
                 "profile_host": profile_host,
                 "./test_package/conanfile.py": test_conanfile,
                 "./test_package/CMakeLists.txt": test_cmakelist})
    client.run("create . -pr:b profile_build -pr:h profile_host")
