import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.xfail(reason="This was using legacy cmake_find_package generator, need to be tested "
                   "with modern, probably move it to elsewhere")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for Apple")
@pytest.mark.tool("cmake")
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
    """)

    client = TestClient()
    client.run("new cmake_lib -d name=hello -d version=0.1")
    client.save({"profile_build": profile_build,
                 "profile_host": profile_host})
    client.run("create . -pr:b profile_build -pr:h profile_host")
