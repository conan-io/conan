import sys
import textwrap

import pytest

from conan.tools.meson import MesonToolchain
from conans.test.utils.tools import TestClient


build_env_1 = textwrap.dedent("""
CFLAGS=-mios-version-min=1 -isysroot ROOT1 -arch armv1
CXXFLAGS=-mios-version-min=2 -isysroot ROOT2 -arch armv2
LDFLAGS=-mios-version-min=3 -isysroot ROOT3 -arch armv3
""")

expected_args_1 = textwrap.dedent("""
c_args = ['-mios-version-min=1', '-isysroot', 'ROOT1', '-arch', 'armv1'] + preprocessor_definitions
c_link_args = ['-mios-version-min=3', '-isysroot', 'ROOT3', '-arch', 'armv3']
cpp_args = ['-mios-version-min=2', '-isysroot', 'ROOT2', '-arch', 'armv2'] + preprocessor_definitions
cpp_link_args = ['-mios-version-min=3', '-isysroot', 'ROOT3', '-arch', 'armv3']
""")

build_env_2 = textwrap.dedent("""
CFLAGS=-isysroot ROOT1 -arch armv1
CXXFLAGS=-mios-version-min=2 -arch armv2
LDFLAGS=-mios-version-min=3 -isysroot ROOT3
""")

expected_args_2 = textwrap.dedent("""
c_args = ['-isysroot', 'ROOT1', '-arch', 'armv1', '-mios-version-min=10.0'] + preprocessor_definitions
c_link_args = ['-mios-version-min=3', '-isysroot', 'ROOT3', '-arch', 'arm64']
cpp_args = ['-mios-version-min=2', '-arch', 'armv2', '-isysroot', '/my/sdk/path'] + preprocessor_definitions
cpp_link_args = ['-mios-version-min=3', '-isysroot', 'ROOT3', '-arch', 'arm64']
""")


build_env_3 = textwrap.dedent("""
CFLAGS=-flag1
CXXFLAGS=-flag2
LDFLAGS=-flag3
""")

expected_args_3 = textwrap.dedent("""
c_args = ['-flag1', '-mios-version-min=10.0', '-isysroot', '/my/sdk/path', '-arch', 'arm64'] + preprocessor_definitions
c_link_args = ['-flag3', '-mios-version-min=10.0', '-isysroot', '/my/sdk/path', '-arch', 'arm64']
cpp_args = ['-flag2', '-mios-version-min=10.0', '-isysroot', '/my/sdk/path', '-arch', 'arm64'] + preprocessor_definitions
cpp_link_args = ['-flag3', '-mios-version-min=10.0', '-isysroot', '/my/sdk/path', '-arch', 'arm64']
""")


@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
@pytest.mark.parametrize("build_env,expected_args", [
    (build_env_1, expected_args_1),
    (build_env_2, expected_args_2),
    (build_env_3, expected_args_3),
])
def test_apple_meson_keep_user_flags(build_env, expected_args):
    default = textwrap.dedent("""
    [settings]
    os=Macos
    arch=x86_64
    compiler=apple-clang
    compiler.version=12.0
    compiler.libcxx=libc++
    build_type=Release
    """)

    cross = textwrap.dedent("""
    [settings]
    os = iOS
    os.version = 10.0
    os.sdk = iphoneos
    arch = armv8
    compiler = apple-clang
    compiler.version = 12.0
    compiler.libcxx = libc++

    [buildenv]
    {build_env}

    [conf]
    tools.apple:sdk_path=/my/sdk/path
    """.format(build_env=build_env))

    _conanfile_py = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.meson import MesonToolchain

    class App(ConanFile):
        settings = "os", "arch", "compiler", "build_type"

        def generate(self):
            tc = MesonToolchain(self)
            tc.generate()
    """)

    t = TestClient()
    t.save({"conanfile.py": _conanfile_py,
            "build_prof": default,
            "host_prof": cross})

    t.run("install . -pr:h host_prof -pr:b build_prof")
    content = t.load(MesonToolchain.cross_filename)
    assert expected_args in content
