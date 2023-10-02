import os.path
import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for Darwin")
@pytest.mark.tool("bazel")
def test_bazel_simple_cross_compilation():
    profile = textwrap.dedent("""
    [settings]
    arch=x86_64
    build_type=Release
    compiler=apple-clang
    compiler.cppstd=gnu17
    compiler.libcxx=libc++
    compiler.version=13.0
    os=Macos
    """)
    profile_host = textwrap.dedent("""
    [settings]
    arch=armv8
    build_type=Release
    compiler=apple-clang
    compiler.cppstd=gnu17
    compiler.libcxx=libc++
    compiler.version=13.0
    os=Macos
    """)
    client = TestClient(path_with_spaces=False)
    client.run("new bazel_lib -d name=myapp -d version=1.0")
    client.save({
        "profile": profile,
        "profile_host": profile_host
    })
    client.run("build . -pr:h profile_host -pr:b profile")
    libmyapp = os.path.join(client.current_folder, "bazel-bin", "main", "libmyapp.a")
    client.run_command(f'otool -hv {libmyapp}')
    assert "ARM64" in client.out
