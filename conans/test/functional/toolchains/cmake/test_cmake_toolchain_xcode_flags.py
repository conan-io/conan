import textwrap
import platform
import os

import pytest

from conans.test.utils.tools import TestClient


def _add_message_status_flags(client):
    cmakelists_path = os.path.join(client.current_folder, "CMakeLists.txt")
    with open(cmakelists_path, "a") as cmakelists_file:
        cmakelists_file.write('message(STATUS "CONAN_C_FLAGS: ${CONAN_C_FLAGS}")\n')
        cmakelists_file.write('message(STATUS "CONAN_CXX_FLAGS: ${CONAN_CXX_FLAGS}")\n')


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.parametrize("op_system,os_version,sdk,arch", [
    ("watchOS", "8.1", "watchos", "armv7k"),
    ("tvOS", "13.2", "appletvos", "armv8")
])
def test_cmake_apple_bitcode_arc_and_visibility_flags_enabled(op_system, os_version, sdk, arch):
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
    _add_message_status_flags(client)
    client.run("install . --profile:build=default --profile:host=host")
    toolchain = client.load(os.path.join("build", "generators", "conan_toolchain.cmake"))
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

    client.run("create . --profile:build=default --profile:host=host -tf None")
    # flags
    assert "-- CONAN_C_FLAGS:  -fembed-bitcode -fobjc-arc" in client.out
    assert "-- CONAN_CXX_FLAGS:  -fembed-bitcode -fvisibility=default -fobjc-arc" in client.out
    assert "[100%] Built target hello" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.parametrize("op_system,os_version,sdk,arch", [
    ("watchOS", "8.1", "watchos", "armv7k"),
    ("tvOS", "13.2", "appletvos", "armv8")
])
def test_cmake_apple_bitcode_arc_and_visibility_flags_enabled_and_xcode_generator(op_system, os_version, sdk, arch):
    """
    Testing when all the Bitcode, ARC and Visibility are enabled, and Xcode as generator.

    Note: When using CMake and Xcode as generator, the C/CXX flags do not need to be appended.
    """
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
    _add_message_status_flags(client)
    client.run("create . --profile:build=default --profile:host=host -tf None "
               "-c tools.cmake.cmaketoolchain:generator=Xcode")
    assert "** BUILD SUCCEEDED **" in client.out
    # flags are not appended when Xcode generator is used
    for line in str(client.out).splitlines():
        if "CONAN_C_FLAGS:" in line:
            assert "-- CONAN_C_FLAGS:" == line.strip()
        if "CONAN_CXX_FLAGS:" in line:
            assert "-- CONAN_CXX_FLAGS:  -stdlib=libc++" == line.strip()
            break


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.parametrize("op_system,os_version,sdk,arch", [
    ("watchOS", "8.1", "watchos", "armv7k"),
    ("tvOS", "13.2", "appletvos", "armv8")
])
def test_cmake_apple_bitcode_arc_and_visibility_flags_disabled(op_system, os_version, sdk, arch):
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
    _add_message_status_flags(client)
    client.run("install . --profile:build=default --profile:host=host")
    toolchain = client.load(os.path.join("build", "generators", "conan_toolchain.cmake"))
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

    client.run("create . --profile:build=default --profile:host=host -tf None")
    # flags
    assert "-- CONAN_C_FLAGS:   -fno-objc-arc" in client.out
    assert "-- CONAN_CXX_FLAGS:   -fvisibility=hidden -fvisibility-inlines-hidden -fno-objc-arc" in client.out
    assert "[100%] Built target hello" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.parametrize("op_system,os_version,sdk,arch", [
    ("watchOS", "8.1", "watchos", "armv7k"),
    ("tvOS", "13.2", "appletvos", "armv8")
])
def test_cmake_apple_bitcode_arc_and_visibility_flags_are_none(op_system, os_version, sdk, arch):
    """
    Testing what happens when any of the Bitcode, ARC or Visibility configurations are not defined.
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
    _add_message_status_flags(client)
    client.run("install . --profile:build=default --profile:host=host")
    toolchain = client.load(os.path.join("build", "generators", "conan_toolchain.cmake"))
    # bitcode
    assert 'set(CMAKE_XCODE_ATTRIBUTE_ENABLE_BITCODE "NO")' not in toolchain
    assert 'set(CMAKE_XCODE_ATTRIBUTE_BITCODE_GENERATION_MODE "bitcode")' not in toolchain
    assert 'set(BITCODE "-fembed-bitcode")' not in toolchain
    # arc
    assert 'set(FOBJC_ARC "-' not in toolchain
    assert 'set(CMAKE_XCODE_ATTRIBUTE_CLANG_ENABLE_OBJC_ARC' not in toolchain
    # visibility
    assert 'set(CMAKE_XCODE_ATTRIBUTE_GCC_SYMBOLS_PRIVATE_EXTERN' not in toolchain
    assert 'set(VISIBILITY "-' not in toolchain

    client.run("create . --profile:build=default --profile:host=host -tf None")
    # flags are not appended
    for flag in ["-fembed-bitcode", "-fno-objc-arc", "-fobjc-arc", "-fvisibility"]:
        assert flag not in client.out
    assert "[100%] Built target hello" in client.out
