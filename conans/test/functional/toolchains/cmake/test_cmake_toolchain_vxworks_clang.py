import platform
import textwrap

import pytest

from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient
from conans.util.files import save


@pytest.fixture
def client():
    c = TestClient()
    save(c.cache.new_config_path, "tools.env.virtualenv:auto_use=True")
    clang_profile = textwrap.dedent("""
        [settings]
        arch=armv7
        build_type=RelWithDebInfo
        compiler=clang
        compiler.libcxx=libstdc++11
        compiler.version=12
        os=VxWorks
        os.version=7

        [buildenv]
        CC=clang
        CXX=clang++
        """)
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conan.tools.cmake import CMake
        from conan.tools.layout import cmake_layout
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "*"
            generators = "CMakeToolchain"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                cmd = os.path.join(self.cpp.build.bindirs[0], "my_app")
                self.run(cmd, env=["conanrunenv"])
        """)
    c.save({"conanfile.py": conanfile,
            "clang": clang_profile,
            "CMakeLists.txt": gen_cmakelists(appname="my_app", appsources=["src/main.cpp"]),
            "src/main.cpp": gen_function_cpp(name="main")})
    return c


@pytest.mark.tool_cmake
@pytest.mark.tool_clang(version="12")
def test_clang_cmake_ninja(client):
    client.run("create . pkg/0.1@ -pr=clang -c tools.cmake.cmaketoolchain:generator=Ninja")
    assert 'cmake -G "Ninja"' in client.out
    assert "main __clang_major__12" in client.out
