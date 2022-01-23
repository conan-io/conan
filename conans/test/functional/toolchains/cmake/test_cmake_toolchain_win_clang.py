import platform
import textwrap

import pytest

from conans.client.tools import environment_append
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
        os=Windows
        arch=x86_64
        build_type=Release
        compiler=clang
        compiler.version=12
        """)
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

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
@pytest.mark.tool_mingw64
@pytest.mark.tool_clang(version="12")
@pytest.mark.skipif(platform.system() != "Windows", reason="requires Win")
def test_clang(client):
    client.run("create . pkg/0.1@ -pr=clang")
    # clang compilations in Windows will use MinGW Makefiles by default
    assert 'cmake -G "MinGW Makefiles"' in client.out
    assert "main __clang_major__12" in client.out
    # Check this! Clang compiler in Windows is reporting MSC_VER and MSVC_LANG!
    assert "main _MSC_VER19" in client.out
    assert "main _MSVC_LANG2014" in client.out


@pytest.mark.tool_cmake
@pytest.mark.tool_clang(version="12")
@pytest.mark.skipif(platform.system() != "Windows", reason="requires Win")
def test_clang_cmake_ninja(client):
    client.run("create . pkg/0.1@ -pr=clang -c tools.cmake.cmaketoolchain:generator=Ninja")
    assert 'cmake -G "Ninja"' in client.out
    assert "main __clang_major__12" in client.out
    # Check this! Clang compiler in Windows is reporting MSC_VER and MSVC_LANG!
    assert "main _MSC_VER19" in client.out
    assert "main _MSVC_LANG2014" in client.out


@pytest.mark.tool_cmake
@pytest.mark.tool_clang(version="12")
@pytest.mark.skipif(platform.system() != "Windows", reason="requires Win")
def test_clang_cmake_ninja_custom_cxx(client):
    with environment_append({"CXX": "/no/exist/clang++"}):
        client.run("create . pkg/0.1@ -pr=clang -c tools.cmake.cmaketoolchain:generator=Ninja",
                   assert_error=True)
        assert 'Could not find compiler' in client.out
        assert '/no/exist/clang++' in client.out

    clang_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        build_type=Release
        compiler=clang
        compiler.version=12
        [buildenv]
        CXX=/no/exist/clang++
        """)
    client.save({"clang":     clang_profile})
    client.run("create . pkg/0.1@ -pr=clang -c tools.cmake.cmaketoolchain:generator=Ninja",
               assert_error=True)
    assert 'Could not find compiler' in client.out
    assert '/no/exist/clang++' in client.out


@pytest.mark.tool_cmake
@pytest.mark.tool_visual_studio(version="16")  # With Clang distributed in VS!
@pytest.mark.skipif(platform.system() != "Windows", reason="requires Win")
def test_clang_cmake_visual(client):
    clang_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        build_type=Release
        compiler=clang
        compiler.version=11
        """)
    # TODO: Clang version is unused, it can change, still 11 from inside VS is used
    client.save({"clang": clang_profile})
    client.run("create . pkg/0.1@ -pr=clang "
               '-c tools.cmake.cmaketoolchain:generator="Visual Studio 16"')
    assert 'cmake -G "Visual Studio 16"' in client.out
    assert "main __clang_major__11" in client.out
    # Check this! Clang compiler in Windows is reporting MSC_VER and MSVC_LANG!
    assert "main _MSC_VER19" in client.out
    assert "main _MSVC_LANG2014" in client.out
