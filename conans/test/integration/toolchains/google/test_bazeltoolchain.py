import os
import textwrap

import pytest

from conan.tools.files import load
from conan.tools.google import BazelToolchain
from conans.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def conanfile():
    return textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.google import BazelToolchain, bazel_layout
        class ExampleConanIntegration(ConanFile):
            settings = "os", "arch", "build_type", "compiler"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}
            generators = 'BazelToolchain'
            def layout(self):
                bazel_layout(self)
    """)


def test_default_bazel_toolchain(conanfile):
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

    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": profile})
    c.run("install . -pr profile")
    content = load(c, os.path.join(c.current_folder, "conan", BazelToolchain.bazelrc_name))
    assert "build:conan-config --cxxopt=-std=gnu++17" in content
    assert "build:conan-config --force_pic=True" in content
    assert "build:conan-config --dynamic_mode=off" in content
    assert "build:conan-config --compilation_mode=opt" in content


def test_bazel_toolchain_and_flags(conanfile):
    profile = textwrap.dedent("""
    [settings]
    arch=x86_64
    build_type=Release
    compiler=apple-clang
    compiler.cppstd=gnu17
    compiler.libcxx=libc++
    compiler.version=13.0
    os=Macos
    [options]
    shared=True
    [conf]
    tools.build:cxxflags=["--flag1", "--flag2"]
    tools.build:cflags+=["--flag3", "--flag4"]
    tools.build:sharedlinkflags+=["--flag5"]
    tools.build:exelinkflags+=["--flag6"]
    tools.build:linker_scripts+=["myscript.sh"]
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": profile})
    c.run("install . -pr profile")
    content = load(c, os.path.join(c.current_folder, "conan", BazelToolchain.bazelrc_name))
    assert "build:conan-config --conlyopt=--flag3 --conlyopt=--flag4" in content
    assert "build:conan-config --cxxopt=-std=gnu++17 --cxxopt=--flag1 --cxxopt=--flag2" in content
    assert "build:conan-config --linkopt=--flag5 --linkopt=--flag6 --linkopt=-T'myscript.sh'" in content
    assert "build:conan-config --force_pic=True" not in content
    assert "build:conan-config --dynamic_mode=fully" in content
    assert "build:conan-config --compilation_mode=opt" in content


def test_bazel_toolchain_and_cross_compilation(conanfile):
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
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": profile,
            "profile_host": profile_host})
    c.run("install . -pr:b profile -pr:h profile_host")
    content = load(c, os.path.join(c.current_folder, "conan", BazelToolchain.bazelrc_name))
    assert "build:conan-config --cpu=darwin_arm64" in content
