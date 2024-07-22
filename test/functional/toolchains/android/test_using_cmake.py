import platform
import tempfile
import textwrap

import pytest

from test.conftest import tools_locations
from conan.test.utils.tools import TestClient


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
    assert "conanfile.py (hello/0.1): Running CMake.build()" in c.out
