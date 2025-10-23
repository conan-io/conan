import textwrap
from conan.test.assets.genconanfile import GenConanfile
import pytest

from conan.test.utils.tools import TestClient
from conan.tools.premake.toolchain import PremakeToolchain


def test_extra_flags_via_conf():
    profile = textwrap.dedent(
        """
        [settings]
        os=Linux
        arch=x86_64
        compiler=gcc
        compiler.version=9
        compiler.cppstd=17
        compiler.libcxx=libstdc++
        build_type=Release

        [conf]
        tools.build:cxxflags=["-flag1", "-flag2"]
        tools.build:cflags=["-flag3", "-flag4"]
        tools.build:sharedlinkflags+=["-flag5"]
        tools.build:exelinkflags+=["-flag6"]
        tools.build:defines=["define1=0"]
    """
    )
    tc = TestClient()
    tc.save(
        {
            "conanfile.txt": "[generators]\nPremakeToolchain",
            "profile": profile,
        }
    )

    tc.run("install . -pr:a=profile")
    content = tc.load(PremakeToolchain.filename)
    assert 'cppdialect "c++17"' in content

    assert (
        """
        filter { files { "**.c" } }
            buildoptions { "-flag3", "-flag4", "-m64" }
        filter {}
        """
        in content
    )

    assert (
        """
        filter { files { "**.cpp", "**.cxx", "**.cc" } }
            buildoptions { "-flag1", "-flag2", "-m64" }
        filter {}
        """
        in content
    )

    assert 'linkoptions { "-flag5", "-flag6", "-m64" }' in content
    assert 'defines { "define1=0", "_GLIBCXX_USE_CXX11_ABI=0" }' in content


def test_project_configuration():
    tc = TestClient(path_with_spaces=False)
    profile = textwrap.dedent(
        """
        [settings]
        arch=armv8
        build_type=Release
        compiler=apple-clang
        compiler.cppstd=gnu17
        compiler.cstd=gnu11
        compiler.libcxx=libc++
        compiler.version=17
        os=Macos
    """
    )
    conanfile = textwrap.dedent(
        """
        from conan import ConanFile
        from conan.tools.layout import basic_layout
        from conan.tools.premake import Premake, PremakeDeps, PremakeToolchain
        import os

        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            name = "pkg"
            version = "1.0"
            options = {"fPIC": [True, False]}
            default_options = {"fPIC": True}

            def layout(self):
                basic_layout(self, src_folder="src")

            def generate(self):
                tc = PremakeToolchain(self)
                tc.extra_defines = ["VALUE=2"]
                tc.extra_cflags = ["-Wextra"]
                tc.extra_cxxflags = ["-Wall", "-Wextra"]
                tc.extra_ldflags = ["-lm"]
                tc.project("main").extra_defines = ["TEST=False"]
                tc.project("test").disable = True
                tc.project("main").extra_cxxflags = ["-FS"]
                tc.generate()
    """
    )
    tc.save({"conanfile.py": conanfile, "profile": profile})
    tc.run("install . -pr:a profile")

    toolchain = tc.load("build-release/conan/conantoolchain.premake5.lua")

    assert 'pic "On"' in toolchain
    assert (
        """
        filter { files { "**.c" } }
            buildoptions { "-Wextra" }
        filter {}
        """
        in toolchain
    )
    assert (
        """
        filter { files { "**.cpp", "**.cxx", "**.cc" } }
            buildoptions { "-stdlib=libc++", "-Wall", "-Wextra" }
        filter {}
        """
        in toolchain
    )
    assert 'linkoptions { "-lm" }' in toolchain
    assert 'defines { "VALUE=2" }' in toolchain
    assert 'linkoptions { "-Wl,-rpath,@loader_path" }' in toolchain
    assert (
        textwrap.dedent(
            """
    project "main"
        -- CXX flags retrieved from CXXFLAGS environment, conan.conf(tools.build:cxxflags), extra_cxxflags and compiler settings
        filter { files { "**.cpp", "**.cxx", "**.cc" } }
            buildoptions { "-stdlib=libc++", "-FS" }
        filter {}
        -- Defines retrieved from DEFINES environment, conan.conf(tools.build:defines) and extra_defines
        defines { "TEST=False" }
        """
        )
        in toolchain
    )
    assert (
        textwrap.dedent(
            """
        project "test"
            kind "None"
        """
        )
        in toolchain
    )


@pytest.mark.parametrize(
    "threads, flags",
    [("posix", "-pthread"), ("wasm_workers", "-sWASM_WORKERS=1")],
)
def test_thread_flags(threads, flags):
    client = TestClient()
    profile = textwrap.dedent(f"""
        [settings]
        arch=wasm64
        build_type=Release
        compiler=emcc
        compiler.cppstd=17
        compiler.threads={threads}
        compiler.libcxx=libc++
        compiler.version=4.0.10
        os=Emscripten
        """)
    client.save(
        {
            "conanfile.py": GenConanfile("pkg", "1.0")
            .with_settings("os", "arch", "compiler", "build_type")
            .with_generator("PremakeToolchain"),
            "profile": profile,
        }
    )
    client.run("install . -pr=./profile")
    toolchain = client.load("conantoolchain.premake5.lua")
    assert (
        """
        filter { files { "**.c" } }
            buildoptions { "-sMEMORY64=1", "%s" }
        filter {}
        """
        % flags
        in toolchain
    )
    assert (
        """
        filter { files { "**.cpp", "**.cxx", "**.cc" } }
            buildoptions { "-stdlib=libc++", "-sMEMORY64=1", "%s" }
        filter {}
        """
        % flags
        in toolchain
    )
    assert 'linkoptions { "-sMEMORY64=1", "%s" }' % flags in toolchain
