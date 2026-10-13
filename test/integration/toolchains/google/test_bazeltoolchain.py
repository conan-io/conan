import os
import textwrap

import pytest

from conan.tools.files import load
from conan.tools.google import BazelToolchain
from conan.test.utils.tools import TestClient


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
    c.run("install . -pr:b profile -pr:h profile")
    content = load(c, os.path.join(c.current_folder, "conan", BazelToolchain.bazelrc_name))
    assert "cc_toolchain(" not in c.load("conan/conan_toolchain/BUILD.bazel")
    assert os.path.exists(os.path.join(c.current_folder, "conan", "BUILD.bazel"))
    assert "try-import %workspace%/conan/conan_bzl.rc" in c.out
    assert "bazel --bazelrc=conan/conan_bzl.rc build --config=conan-config //..." in c.out
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
    assert "--cpu" not in content
    assert "build:conan-config --platforms=//conan/conan_toolchain:target" in content


def test_toolchain_attributes_and_conf_priority():
    """
    Tests that all the attributes are appearing correctly in the conan_bzl.rc even defining
    some conf variables
    """
    profile = textwrap.dedent("""
    [settings]
    arch=x86_64
    build_type=Release
    compiler=apple-clang
    compiler.cppstd=gnu17
    compiler.libcxx=libc++
    compiler.version=13.0
    os=Macos
    [conf]
    tools.build:cxxflags=["--flag1"]
    tools.build:cflags+=["--flag3"]
    tools.build:sharedlinkflags+=["--linkflag5"]
    tools.build:exelinkflags+=["--linkflag6"]
    """)
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.google import BazelToolchain
    class ExampleConanIntegration(ConanFile):
        settings = "os", "arch", "build_type", "compiler"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": False, "fPIC": True}

        def generate(self):
            bz = BazelToolchain(self)
            bz.copt = ["copt1"]
            bz.conlyopt = ["conly1"]
            bz.cxxopt = ["cxxopt1"]
            bz.linkopt = ["linkopt1"]
            bz.force_pic = True
            bz.dynamic_mode = "auto"
            bz.compilation_mode = "fastbuild"
            bz.compiler = "gcc"
            bz.cpu = "armv8"
            bz.crosstool_top = "my_crosstool"
            bz.generate()
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": profile})
    # Same profile for build and host, so platform generation does not depend on the machine.
    c.run("install . -pr:b profile -pr:h profile")
    content = load(c, os.path.join(c.current_folder, BazelToolchain.bazelrc_name))
    expected = textwrap.dedent("""\
    # Automatic bazelrc file created by Conan
    build:conan-config --copt=copt1
    build:conan-config --conlyopt=conly1 --conlyopt=--flag3
    build:conan-config --cxxopt=-std=gnu++17 --cxxopt=cxxopt1 --cxxopt=--flag1
    build:conan-config --linkopt=linkopt1 --linkopt=--linkflag5 --linkopt=--linkflag6
    build:conan-config --force_pic=True
    build:conan-config --dynamic_mode=auto
    build:conan-config --compilation_mode=fastbuild
    build:conan-config --compiler=gcc
    build:conan-config --cpu=armv8
    build:conan-config --crosstool_top=my_crosstool
    build:conan-config --platforms=//conan_toolchain:target
    build:conan-config --host_platform=//conan_toolchain:host
    """)
    assert expected == content


def _linux_profile(arch="x86_64", compiler="gcc", libcxx="libstdc++11", cc="gcc", cxx="g++"):
    return textwrap.dedent(f"""
    [settings]
    arch={arch}
    build_type=Release
    compiler={compiler}
    compiler.cppstd=gnu17
    compiler.libcxx={libcxx}
    compiler.version=11
    os=Linux
    [conf]
    tools.build:compiler_executables={{'c': '/opt/bin/{cc}', 'cpp': '/opt/bin/{cxx}'}}
    """)


def test_native_build_generates_platforms(conanfile):
    """A native gcc Linux build writes platforms and one cc_toolchain."""
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile": _linux_profile() + "tools.build:sysroot=/opt/sysroot\n"})
    c.run("install . -pr:b profile -pr:h profile")
    content = c.load("conan/conan_bzl.rc")
    assert "build:conan-config --platforms=//conan/conan_toolchain:target" in content
    assert "build:conan-config --host_platform=//conan/conan_toolchain:host" in content
    assert "-m64" not in content
    build = c.load("conan/conan_toolchain/BUILD.bazel")
    assert '"gcc": "/opt/bin/gcc"' in build
    assert '"ar": "/opt/bin/ar"' in build
    assert '"-m64"' in build
    assert '"-lstdc++"' in build
    assert 'builtin_sysroot = "/opt/sysroot"' in build
    assert 'name = "cc_for_target"' in build
    assert "cc_for_host" not in build
    assert '"//conan/conan_toolchain:cc_for_target"' in c.load("conan/conan_toolchain.MODULE.bazel")


def test_clang_libcxx_is_a_toolchain_flag(conanfile):
    """clang libc++ becomes -stdlib on the toolchain."""
    c = TestClient()
    profile = _linux_profile(compiler="clang", libcxx="libc++", cc="clang", cxx="clang++")
    c.save({"conanfile.py": conanfile, "profile": profile})
    c.run("install . -pr:b profile -pr:h profile")
    build = c.load("conan/conan_toolchain/BUILD.bazel")
    assert '"gcc": "/opt/bin/clang"' in build
    assert '"-stdlib=libc++"' in build


def test_msvc_cross_arm64(conanfile):
    """An x64 to arm64 msvc cross build writes one cl.exe toolchain per profile."""
    def profile(arch, cl):
        return textwrap.dedent(f"""
        [settings]
        arch={arch}
        build_type=Release
        compiler=msvc
        compiler.version=193
        compiler.runtime=static
        compiler.runtime_type=Release
        os=Windows
        [conf]
        tools.build:compiler_executables={{'c': '{cl}', 'cpp': '{cl}'}}
        """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile_build": profile("x86_64", "C:/VS/x64/cl.exe"),
            "profile_host": profile("armv8", "C:/VS/arm64/cl.exe")})
    c.run("install . -pr:b profile_build -pr:h profile_host")
    assert "build:conan-config --features=static_link_msvcrt" in c.load("conan/conan_bzl.rc")
    build = c.load("conan/conan_toolchain/BUILD.bazel")
    assert "@rules_cc//cc/private/toolchain:windows_cc_toolchain_config.bzl" in build
    assert "unix_cc_toolchain_config" not in build
    assert 'compiler = "msvc-cl"' in build
    assert 'cpu = "x64_windows"' in build
    assert "@platforms//cpu:aarch64" in build
    assert 'msvc_cl_path = "C:/VS/arm64/cl.exe"' in build
    assert 'msvc_link_path = "C:/VS/arm64/link.exe"' in build
    assert '"/MACHINE:ARM64"' in build
    assert 'msvc_cl_path = "C:/VS/x64/cl.exe"' in build
    assert '"/MACHINE:X64"' in build
    assert 'name = "cc_for_host"' in build


def test_cross_build_generates_platforms(conanfile):
    """A gcc Linux cross build writes one cc_toolchain per profile."""
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile_build": _linux_profile(),
            "profile_host": _linux_profile("armv8", cc="aarch64-linux-gnu-gcc",
                                           cxx="aarch64-linux-gnu-g++")})
    c.run("install . -pr:b profile_build -pr:h profile_host")
    build = c.load("conan/conan_toolchain/BUILD.bazel")
    assert "@platforms//cpu:aarch64" in build
    assert '"gcc": "/opt/bin/aarch64-linux-gnu-gcc"' in build
    assert '"ar": "/opt/bin/aarch64-linux-gnu-ar"' in build
    assert '"gcc": "/opt/bin/gcc"' in build
    module = c.load("conan/conan_toolchain.MODULE.bazel")
    assert "cc_for_host" in module
    assert "cc_for_target" in module


@pytest.mark.parametrize("setting, value", [("os", "Linux"), ("arch", "x86_64")])
def test_missing_os_or_arch_skips_platforms(setting, value):
    """Unset os or arch omits the platforms. The bazelrc is still written."""
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        class Consumer(ConanFile):
            settings = "{setting}"
            generators = "BazelToolchain"
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile})
    c.run(f"install . -s {setting}={value}")
    content = load(c, os.path.join(c.current_folder, BazelToolchain.bazelrc_name))
    assert "build:conan-config --dynamic_mode=off" in content
    assert "--platforms" not in content
    assert not os.path.exists(os.path.join(c.current_folder, "conan_toolchain.MODULE.bazel"))


def test_unmapped_arch_fails(conanfile):
    """An arch without a platforms mapping fails the install."""
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile_build": _linux_profile(),
            "profile_host": _linux_profile("wasm")})
    c.run("install -pr:b profile_build -pr:h profile_host", assert_error=True)
    assert "Cannot map os='Linux' arch='wasm' to Bazel platform constraints." in c.out
