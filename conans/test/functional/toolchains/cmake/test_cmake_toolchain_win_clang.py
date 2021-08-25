import platform
import textwrap

import pytest

from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


@pytest.mark.tool_mingw64
@pytest.mark.tool_clang(version="12")
@pytest.mark.skipif(platform.system() != "Windows", reason="requires Win")
def test_clang():
    c = TestClient()
    clang_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        build_type=Release
        compiler=clang
        compiler.version=12

        [buildenv]
        CC=clang
        CXX=clang++
        RC=clang
        """)
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "*"
            generators = "CMakeToolchain", "VirtualBuildEnv"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)
    c.save({"conanfile.py": conanfile,
            "clang": clang_profile,
            "CMakeLists.txt": gen_cmakelists(appname="my_app", appsources=["main.cpp"]),
            "main.cpp": gen_function_cpp(name="main")})
    c.run("create . pkg/0.1@ -pr=clang")
    print(c.out)

