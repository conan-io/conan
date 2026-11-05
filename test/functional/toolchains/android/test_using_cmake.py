import os
import platform
import tempfile
import textwrap

import pytest

from test.conftest import tools_locations
from conan.test.utils.tools import TestClient


@pytest.mark.slow
@pytest.mark.tool("cmake", "3.23")  # Android complains if <3.19
@pytest.mark.tool("ninja")  # so it easily works in Windows too
@pytest.mark.tool("android_ndk")
@pytest.mark.skipif(platform.system() != "Darwin", reason="NDK only installed on MAC")
def test_use_cmake_toolchain():
    """ This is the naive approach, we follow instruction from CMake in its documentation
        https://cmake.org/cmake/help/latest/manual/cmake-toolchains.7.html#cross-compiling-for-android
    """
    # Overriding the default folders, so they are in the same unit drive in Windows
    # otherwise AndroidNDK FAILS to build, it needs using the same unit drive
    c = TestClient(cache_folder=tempfile.mkdtemp(),
                   current_folder=tempfile.mkdtemp())
    c.run("new cmake_lib -d name=hello -d version=0.1")
    ndk_path = tools_locations["android_ndk"]["system"]["path"][platform.system()]
    android = textwrap.dedent(f"""
       [settings]
       os=Android
       os.api_level=23
       arch=x86_64
       compiler=clang
       compiler.version=12
       compiler.libcxx=c++_shared
       build_type=Release
       [conf]
       tools.android:ndk_path={ndk_path}
       tools.cmake.cmaketoolchain:generator=Ninja
       """)
    c.save({"android": android})
    c.run('create . --profile:host=android')
    assert "hello/0.1 (test package): Running test()" in c.out

    # Build locally
    c.run('build . --profile:host=android')
    assert "Running CMake.build()" in c.out


@pytest.mark.tool("cmake", "3.23")  # CMP0126 exists since CMake 3.21
@pytest.mark.tool("ninja")
@pytest.mark.parametrize("cmake_min_version", ["3.15", "3.21"])
def test_android_abi_cache_variable(cmake_min_version):
    """
    ANDROID_ABI is set both as a normal and as a cache variable (IDEs read it from
    CMakeCache.txt). With CMP0126 NEW, a CACHE set() doesn't remove an existing normal variable,
    so an ANDROID_ABI previously defined (here by the user_toolchain) must not shadow the one
    passed to the NDK.
    Uses a mocked NDK toolchain that just reports the ANDROID_ABI it receives.
    """
    c = TestClient()
    ndk_path = os.path.join(c.current_folder, "fake_ndk").replace("\\", "/")
    user_toolchain = os.path.join(c.current_folder, "user_toolchain.cmake").replace("\\", "/")
    android = textwrap.dedent(f"""
        [settings]
        os=Android
        os.api_level=23
        compiler=clang
        compiler.version=18
        compiler.libcxx=c++_shared
        build_type=Release
        [conf]
        tools.android:ndk_path={ndk_path}
        tools.cmake.cmaketoolchain:user_toolchain=["{user_toolchain}"]
        tools.cmake.cmaketoolchain:generator=Ninja
        """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)
    cmakelists = textwrap.dedent(f"""
        cmake_minimum_required(VERSION {cmake_min_version})
        project(pkg LANGUAGES NONE)
        message(STATUS "-- project - ANDROID_ABI=${{ANDROID_ABI}}")
        message(STATUS "-- project - cache ANDROID_ABI=$CACHE{{ANDROID_ABI}}")
        """)
    c.save({"android": android,
            "conanfile.py": conanfile,
            "CMakeLists.txt": cmakelists,
            "user_toolchain.cmake": "set(ANDROID_ABI armeabi-v7a)",
            "fake_ndk/build/cmake/android.toolchain.cmake":
                'message(STATUS "-- NDK - ANDROID_ABI=${ANDROID_ABI}")'})

    arch, abi = "armv8", "arm64-v8a"
    c.run(f"build . -pr:h=android -s:h arch={arch}")
    assert f"-- NDK - ANDROID_ABI={abi}" in c.out
    assert f"-- project - ANDROID_ABI={abi}" in c.out
    assert f"-- project - cache ANDROID_ABI={abi}" in c.out
    assert "armeabi-v7a" not in c.out
    cmake_cache = c.load("CMakeCache.txt")
    assert f"ANDROID_ABI:STRING={abi}" in cmake_cache
