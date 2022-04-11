import textwrap
import platform
import os

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.parametrize("op_system,os_version,sdk,arch", [
    ("watchOS", "8.1", "watchos", "armv7k"),
    ("tvOS", "13.2", "appletvos", "armv8")
])
def test_xcode_bitcode_arc_and_visibility_flags_enabled(op_system, os_version, sdk, arch):
    profile = textwrap.dedent("""
        include(default)
        [settings]
        os={}
        os.version={}
        os.sdk={}
        arch={}
        [conf]
        tools.apple:enable_bitcode=True
        tools.apple:enable_arc=True
        tools.apple:enable_visibility=True
    """.format(op_system, os_version, sdk, arch))

    client = TestClient(path_with_spaces=False)
    client.save({"host": profile}, clean_first=True)
    client.run("new hello/0.1 --template=cmake_lib")
    client.run("install . --profile:build=default --profile:host=host")
    toolchain = client.load(os.path.join("cmake-build-release", "conan", "conan_toolchain.cmake"))
    # bitcode
    assert 'set(CMAKE_XCODE_ATTRIBUTE_ENABLE_BITCODE "YES")' in toolchain
    assert 'set(CMAKE_XCODE_ATTRIBUTE_BITCODE_GENERATION_MODE "bitcode")' in toolchain
    assert 'set(BITCODE "-fembed-bitcode")' in toolchain
    # arc
    assert 'set(FOBJC_ARC "-fobjc-arc")' in toolchain
    assert 'set(CMAKE_XCODE_ATTRIBUTE_CLANG_ENABLE_OBJC_ARC "YES")' in toolchain
    # visibility
    assert 'set(CMAKE_XCODE_ATTRIBUTE_GCC_SYMBOLS_PRIVATE_EXTERN "NO")' in toolchain
    assert 'set(VISIBILITY "-fvisibility=default")' in toolchain
    # flags
    assert 'string(APPEND CONAN_C_FLAGS " ${BITCODE} ${FOBJC_ARC}")' in toolchain
    assert 'string(APPEND CONAN_CXX_FLAGS " ${BITCODE} ${VISIBILITY} ${FOBJC_ARC}")' in toolchain

    client.run("create . --profile:build=default --profile:host=host -tf None")
    assert "[100%] Built target hello" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.parametrize("op_system,os_version,sdk,arch", [
    ("watchOS", "8.1", "watchos", "armv7k"),
    ("tvOS", "13.2", "appletvos", "armv8")
])
def test_xcode_bitcode_arc_and_visibility_flags_disabled(op_system, os_version, sdk, arch):
    profile = textwrap.dedent("""
        include(default)
        [settings]
        os={}
        os.version={}
        os.sdk={}
        arch={}
        [conf]
        tools.apple:enable_bitcode=False
        tools.apple:enable_arc=False
        tools.apple:enable_visibility=False
    """.format(op_system, os_version, sdk, arch))

    client = TestClient(path_with_spaces=False)
    client.save({"host": profile}, clean_first=True)
    client.run("new hello/0.1 --template=cmake_lib")
    client.run("install . --profile:build=default --profile:host=host")
    toolchain = client.load(os.path.join("cmake-build-release", "conan", "conan_toolchain.cmake"))
    # bitcode
    assert 'set(CMAKE_XCODE_ATTRIBUTE_ENABLE_BITCODE "NO")' in toolchain
    assert 'set(CMAKE_XCODE_ATTRIBUTE_BITCODE_GENERATION_MODE "bitcode")' not in toolchain
    assert 'set(BITCODE "-fembed-bitcode")' not in toolchain
    # arc
    assert 'set(FOBJC_ARC "-fno-objc-arc")' in toolchain
    assert 'set(CMAKE_XCODE_ATTRIBUTE_CLANG_ENABLE_OBJC_ARC "NO")' in toolchain
    # visibility
    assert 'set(CMAKE_XCODE_ATTRIBUTE_GCC_SYMBOLS_PRIVATE_EXTERN "YES")' in toolchain
    assert 'set(VISIBILITY "-fvisibility=hidden -fvisibility-inlines-hidden")' in toolchain
    # flags
    assert 'string(APPEND CONAN_C_FLAGS " ${BITCODE} ${FOBJC_ARC}")' in toolchain
    assert 'string(APPEND CONAN_CXX_FLAGS " ${BITCODE} ${VISIBILITY} ${FOBJC_ARC}")' in toolchain

    client.run("create . --profile:build=default --profile:host=host -tf None")
    assert "[100%] Built target hello" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.parametrize("op_system,os_version,sdk,arch", [
    ("watchOS", "8.1", "watchos", "armv7k"),
    ("tvOS", "13.2", "appletvos", "armv8")
])
def test_xcode_bitcode_arc_and_visibility_flags_are_none(op_system, os_version, sdk, arch):
    """
    Testing what happens when any of the Bitcode, ARC or Visibility configurations are not defined.

    Note: If cross-compiling to watchOS or tvOS, bitcode will be enabled by default.
    """
    profile = textwrap.dedent("""
        include(default)
        [settings]
        os={}
        os.version={}
        os.sdk={}
        arch={}
    """.format(op_system, os_version, sdk, arch))

    client = TestClient(path_with_spaces=False)
    client.save({"host": profile}, clean_first=True)
    client.run("new hello/0.1 --template=cmake_lib")
    client.run("install . --profile:build=default --profile:host=host")
    toolchain = client.load(os.path.join("cmake-build-release", "conan", "conan_toolchain.cmake"))
    # bitcode is enabled by default
    assert 'set(CMAKE_XCODE_ATTRIBUTE_ENABLE_BITCODE "YES")' in toolchain
    assert 'set(CMAKE_XCODE_ATTRIBUTE_BITCODE_GENERATION_MODE "bitcode")' in toolchain
    assert 'set(BITCODE "-fembed-bitcode")' in toolchain
    # arc
    assert 'set(FOBJC_ARC "-' not in toolchain
    assert 'set(CMAKE_XCODE_ATTRIBUTE_CLANG_ENABLE_OBJC_ARC' not in toolchain
    # visibility
    assert 'set(CMAKE_XCODE_ATTRIBUTE_GCC_SYMBOLS_PRIVATE_EXTERN' not in toolchain
    assert 'set(VISIBILITY "-' not in toolchain
    # flags
    assert 'string(APPEND CONAN_C_FLAGS " ${BITCODE} ${FOBJC_ARC}")' in toolchain
    assert 'string(APPEND CONAN_CXX_FLAGS " ${BITCODE} ${VISIBILITY} ${FOBJC_ARC}")' in toolchain

    client.run("create . --profile:build=default --profile:host=host -tf None")
    assert "[100%] Built target hello" in client.out
