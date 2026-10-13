import os
import platform
import textwrap

import pytest

from conan.test.assets.sources import gen_function_cpp, gen_function_h
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient


@pytest.mark.slow
@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for Darwin")
@pytest.mark.tool("bazel", "6.x")  # not working for Bazel 7.x
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
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.google import Bazel, bazel_layout

    class MyappConan(ConanFile):
        name = "myapp"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"
        generators = "BazelToolchain"

        def config_options(self):
            if self.settings.os == "Windows":
                del self.options.fPIC

        def layout(self):
            bazel_layout(self)

        def build(self):
            bazel = Bazel(self)
            bazel.build()
    """)
    BUILD = textwrap.dedent("""
    cc_library(
        name = "myapp",
        srcs = ["myapp.cpp"],
        hdrs = ["myapp.h"],
    )
    """)
    client = TestClient(path_with_spaces=False)
    bazel_root_dir = temp_folder(path_with_spaces=False).replace("\\", "/")
    client.save({
        "profile": profile,
        "profile_host": profile_host,
        "conanfile.py": conanfile,
        "WORKSPACE": "",
        ".bazelrc": f"startup --output_user_root={bazel_root_dir}",
        "main/BUILD": BUILD,
        "main/myapp.cpp": gen_function_cpp(name="myapp"),
        "main/myapp.h": gen_function_h(name="myapp"),

    })
    client.run("build . -pr:h profile_host -pr:b profile")
    libmyapp = os.path.join(client.current_folder, "bazel-bin", "main", "libmyapp.a")
    client.run_command(f'otool -hv {libmyapp}')
    assert "ARM64" in client.out


@pytest.mark.slow
@pytest.mark.skipif(platform.system() != "Linux", reason="Needs the arm-linux-gnueabihf gcc")
@pytest.mark.parametrize("bazel", [pytest.param(version, marks=pytest.mark.tool("bazel", version))
                                   for version in ("7.x", "8.x", "9.x")])
def test_bazel_gcc_cross_compilation(bazel):
    """BazelToolchain generates the cc_toolchain of the host profile and Bazel builds with it."""
    profile_host = textwrap.dedent("""
    [settings]
    arch=armv7hf
    build_type=Release
    compiler=gcc
    compiler.cppstd=17
    compiler.libcxx=libstdc++11
    compiler.version=13
    os=Linux
    [conf]
    tools.build:compiler_executables={"c": "arm-linux-gnueabihf-gcc", "cpp": "arm-linux-gnueabihf-g++"}
    """)
    client = TestClient(path_with_spaces=False)
    output_root = temp_folder(path_with_spaces=False)
    client.run(f"new bazel_7_exe -d name=myapp -d version=1.0 -d output_root_dir={output_root}")
    client.save({"profile_host": profile_host})
    client.run("build . -pr:h profile_host")
    myapp = os.path.join(client.current_folder, "bazel-bin", "main", "myapp")
    client.run_command(f'readelf -h "{myapp}"')
    assert "ELF32" in client.out
    assert "Machine:                           ARM" in client.out
