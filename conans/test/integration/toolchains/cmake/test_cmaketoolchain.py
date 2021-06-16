import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_cross_build():
    windows_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        """)
    rpi_profile = textwrap.dedent("""
        [settings]
        os=Linux
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        arch=armv8
        build_type=Release
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "rpi": rpi_profile,
                 "windows": windows_profile})
    client.run("install . --profile:build=windows --profile:host=rpi")
    toolchain = client.load("conan_toolchain.cmake")

    assert "set(CMAKE_SYSTEM_NAME Linux)" in toolchain
    assert "set(CMAKE_SYSTEM_PROCESSOR armv8)" in toolchain


def test_cross_build_conf():
    windows_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        """)
    rpi_profile = textwrap.dedent("""
        [settings]
        os=Linux
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        arch=armv8
        build_type=Release

        [conf]
        tools.cmake.cmaketoolchain:system_name = Custom
        tools.cmake.cmaketoolchain:system_version= 42
        tools.cmake.cmaketoolchain:system_processor = myarm
        """)

    client = TestClient(path_with_spaces=False)

    conanfile = GenConanfile().with_settings("os", "arch", "compiler", "build_type")\
        .with_generator("CMakeToolchain")
    client.save({"conanfile.py": conanfile,
                "rpi": rpi_profile,
                 "windows": windows_profile})
    client.run("install . --profile:build=windows --profile:host=rpi")
    toolchain = client.load("conan_toolchain.cmake")

    assert "set(CMAKE_SYSTEM_NAME Custom)" in toolchain
    assert "set(CMAKE_SYSTEM_VERSION 42)" in toolchain
    assert "set(CMAKE_SYSTEM_PROCESSOR myarm)" in toolchain
