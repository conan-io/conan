import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Requires Xcode")
@pytest.mark.tool("cmake")
@pytest.mark.tool("ninja")
@pytest.mark.parametrize("os_settings, expected_platform", [
    # https://github.com/conan-io/conan/issues/18466
    ("os=iOS\nos.sdk=iphoneos\nos.version=13.0", "platform 2"),
    # https://github.com/conan-io/conan/issues/13555
    ("os=Macos\nos.subsystem=catalyst\nos.subsystem.ios_version=14.0", "platform 6"),
], ids=["ios", "catalyst"])
def test_swift_cross_build(os_settings, expected_platform):
    """ swiftc does not derive its target from the SDK, without
        CMAKE_Swift_COMPILER_TARGET it would target the host.
        Ninja is the recommended generator: Xcode ignores that variable
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class Lib(ConanFile):
            name = "greet"
            version = "1.0"
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeToolchain"
            exports_sources = "CMakeLists.txt", "greet.swift"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                self.run(f'otool -l "{self.build_folder}/libgreet.a"')
        """)
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(greet LANGUAGES Swift)
        add_library(greet STATIC greet.swift)
        """)
    profile = textwrap.dedent("""
        [settings]
        {os_settings}
        arch=armv8
        compiler=apple-clang
        compiler.version=15
        compiler.libcxx=libc++
        build_type=Release
        [conf]
        tools.cmake.cmaketoolchain:generator=Ninja
        """).format(os_settings=os_settings)
    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": cmakelists,
                 "greet.swift": 'public func greet() -> String { return "hi" }',
                 "profile": profile})
    client.run("create . -pr:h=profile")
    # it would be "platform 1" (macOS) if swiftc had targeted the host
    assert expected_platform in client.out
