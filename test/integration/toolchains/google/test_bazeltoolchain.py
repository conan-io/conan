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
    c.run("install . -pr profile")
    content = load(c, os.path.join(c.current_folder, "conan", BazelToolchain.bazelrc_name))
    build = load(c, os.path.join(c.current_folder, "conan", "conan_toolchain", "BUILD.bazel"))
    assert "cc_toolchain(" not in build
    assert os.path.exists(os.path.join(c.current_folder, "conan", "BUILD.bazel"))
    assert not os.path.exists(os.path.join(c.current_folder, ".bazelrc"))
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


def _linux_profile(arch="x86_64"):
    return textwrap.dedent(f"""
    [settings]
    arch={arch}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)


def test_native_build_generates_platforms(conanfile):
    """A native gcc Linux build writes platforms and one cc_toolchain."""
    profile = _linux_profile() + textwrap.dedent("""
    [conf]
    tools.build:compiler_executables={'c': '/opt/bin/gcc', 'cpp': '/opt/bin/g++'}
    tools.build:sysroot=/opt/sysroot
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile, "profile": profile})
    c.run("install . -pr:b profile -pr:h profile")
    content = load(c, os.path.join(c.current_folder, "conan", BazelToolchain.bazelrc_name))
    assert "build:conan-config --platforms=//conan/conan_toolchain:target" in content
    assert "build:conan-config --host_platform=//conan/conan_toolchain:host" in content
    assert "-m64" not in content
    build = load(c, os.path.join(c.current_folder, "conan", "conan_toolchain", "BUILD.bazel"))
    assert '"gcc": "/opt/bin/gcc"' in build
    assert '"ar": "/opt/bin/ar"' in build
    assert '"-m64"' in build
    assert 'builtin_sysroot = "/opt/sysroot"' in build
    assert 'name = "cc_for_target"' in build
    assert "cc_for_host" not in build
    module = load(c, os.path.join(c.current_folder, "conan", "conan_toolchain.MODULE.bazel"))
    assert '"//conan/conan_toolchain:cc_for_target"' in module


def test_clang_libcxx_is_a_toolchain_flag(conanfile):
    """clang libc++ becomes -stdlib on the toolchain."""
    profile = textwrap.dedent("""
    [settings]
    arch=x86_64
    build_type=Release
    compiler=clang
    compiler.cppstd=gnu17
    compiler.libcxx=libc++
    compiler.version=15
    os=Linux
    [conf]
    tools.build:compiler_executables={'c': '/opt/bin/clang', 'cpp': '/opt/bin/clang++'}
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile, "profile": profile})
    c.run("install . -pr:b profile -pr:h profile")
    build = load(c, os.path.join(c.current_folder, "conan", "conan_toolchain", "BUILD.bazel"))
    assert '"gcc": "/opt/bin/clang"' in build
    assert '"-stdlib=libc++"' in build


def test_cross_build_generates_platforms(conanfile):
    """A gcc Linux cross build writes one cc_toolchain per profile."""
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "profile_build": _linux_profile() + textwrap.dedent("""
            [conf]
            tools.build:compiler_executables={'c': '/opt/host/gcc', 'cpp': '/opt/host/g++'}
            """),
            "profile_host": _linux_profile("armv8") + (
                "[conf]\n"
                "tools.build:compiler_executables="
                "{'c': '/opt/cross/aarch64-linux-gnu-gcc', "
                "'cpp': '/opt/cross/aarch64-linux-gnu-g++'}\n"
            )})
    c.run("install . -pr:b profile_build -pr:h profile_host")
    build = load(c, os.path.join(c.current_folder, "conan", "conan_toolchain", "BUILD.bazel"))
    assert "@platforms//cpu:aarch64" in build
    assert '"gcc": "/opt/cross/aarch64-linux-gnu-gcc"' in build
    assert '"ar": "/opt/cross/aarch64-linux-gnu-ar"' in build
    assert '"gcc": "/opt/host/gcc"' in build
    assert 'name = "cc_for_host"' in build
    module = load(c, os.path.join(c.current_folder, "conan", "conan_toolchain.MODULE.bazel"))
    assert "cc_for_host" in module
    assert "cc_for_target" in module


@pytest.mark.parametrize("declared, args", [
    ("", ""),
    ("settings = 'os'", "-s os=Linux"),
    ("settings = 'arch'", "-s arch=x86_64"),
    ("settings = 'build_type'", "-s build_type=Release"),
])
def test_missing_os_or_arch_skips_platforms(declared, args):
    """Unset os or arch omits the platforms. The bazelrc is still written."""
    settings_line = f"\n            {declared}" if declared else ""
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        class Consumer(ConanFile):
            generators = "BazelToolchain"{settings_line}
    """)
    c = TestClient()
    c.save({"conanfile.py": conanfile})
    c.run(f"install . {args}")
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
