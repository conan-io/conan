import sys
import textwrap

import pytest

from conan.tools.meson import MesonToolchain
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
def test_apple_meson_keep_user_custom_flags():
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

    [conf]
    tools.apple:sdk_path=/my/sdk/path
    """)

    _conanfile_py = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.meson import MesonToolchain

    class App(ConanFile):
        settings = "os", "arch", "compiler", "build_type"

        def generate(self):
            tc = MesonToolchain(self)
            # Customized apple flags
            tc.apple_arch_flag = ['-arch', 'myarch']
            tc.apple_isysroot_flag = ['-isysroot', '/other/sdk/path']
            tc.apple_min_version_flag = ['-otherminversion=10.7']
            tc.generate()
    """)

    t = TestClient()
    t.save({"conanfile.py": _conanfile_py,
            "build_prof": default,
            "host_prof": cross})

    t.run("install . -pr:h host_prof -pr:b build_prof")
    content = t.load(MesonToolchain.cross_filename)
    assert "c_args = ['-isysroot', '/other/sdk/path', '-arch', 'myarch', '-otherminversion=10.7']" in content
    assert "c_link_args = ['-isysroot', '/other/sdk/path', '-arch', 'myarch', '-otherminversion=10.7']" in content
    assert "cpp_args = ['-isysroot', '/other/sdk/path', '-arch', 'myarch', '-otherminversion=10.7']" in content
    assert "cpp_link_args = ['-isysroot', '/other/sdk/path', '-arch', 'myarch', '-otherminversion=10.7']" in content


@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
def test_extra_flags_via_conf():
    profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        compiler=gcc
        compiler.version=9
        compiler.cppstd=17
        compiler.libcxx=libstdc++11
        build_type=Release

        [buildenv]
        CFLAGS=-flag0 -other=val
        CXXFLAGS=-flag0 -other=val
        LDFLAGS=-flag0 -other=val

        [conf]
        tools.build:cxxflags=["-flag1", "-flag2"]
        tools.build:cflags=["-flag3", "-flag4"]
        tools.build:sharedlinkflags+=["-flag5"]
        tools.build:exelinkflags+=["-flag6"]
   """)
    t = TestClient()
    t.save({"conanfile.txt": "[generators]\nMesonToolchain",
            "profile": profile})

    t.run("install . -pr=profile")
    content = t.load(MesonToolchain.native_filename)
    assert "cpp_args = ['-flag0', '-other=val', '-flag1', '-flag2']" in content
    assert "c_args = ['-flag0', '-other=val', '-flag3', '-flag4']" in content
    assert "c_link_args = ['-flag0', '-other=val', '-flag5', '-flag6']" in content
    assert "cpp_link_args = ['-flag0', '-other=val', '-flag5', '-flag6']" in content


@pytest.mark.skipif(sys.version_info.major == 2, reason="Meson not supported in Py2")
def test_correct_quotes():
    profile = textwrap.dedent("""
       [settings]
       os=Windows
       arch=x86_64
       compiler=gcc
       compiler.version=9
       compiler.cppstd=17
       compiler.libcxx=libstdc++11
       build_type=Release
       """)
    t = TestClient()
    t.save({"conanfile.txt": "[generators]\nMesonToolchain",
            "profile": profile})

    t.run("install . -pr=profile")
    content = t.load(MesonToolchain.native_filename)
    assert "cpp_std = 'c++17'" in content
    assert "backend = 'ninja'" in content
    assert "buildtype = 'release'" in content
