import platform
import re
import textwrap

import pytest

from conans.client.tools import environment_append
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_cpp
from conans.test.functional.utils import check_vs_runtime
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
                self.output.info("MYCMD={}!".format(os.path.abspath(cmd)))
                self.run(cmd)
        """)
    c.save({"conanfile.py": conanfile,
            "clang": clang_profile,
            "CMakeLists.txt": gen_cmakelists(appname="my_app", appsources=["src/main.cpp"]),
            "src/main.cpp": gen_function_cpp(name="main")})
    return c


@pytest.mark.tool_cmake
@pytest.mark.tool_clang(version="12")
@pytest.mark.skipif(platform.system() != "Windows", reason="requires Win")
class TestClangVSRuntime:
    """ External LLVM/clang, with different CMake generators
    """

    @pytest.mark.tool_mingw64
    @pytest.mark.tool_visual_studio(version="17")
    @pytest.mark.tool_clang(version="12")  # repeated, for priority
    @pytest.mark.parametrize("runtime", ["static", "dynamic"])
    def test_clang_vs_runtime(self, client, runtime):
        """ compiling with an LLVM-clang installed, which uses by default the
        VS runtime
        """
        client.run("create . pkg/0.1@ -pr=clang "
                   "-s compiler.runtime_version=v143 "
                   "-s compiler.runtime={}".format(runtime))
        # clang compilations in Windows will use MinGW Makefiles by default
        assert 'cmake -G "MinGW Makefiles"' in client.out
        assert "main __clang_major__12" in client.out
        # Check this! Clang compiler in Windows is reporting MSC_VER and MSVC_LANG!
        assert "main _MSC_VER193" in client.out
        assert "main _MSVC_LANG2014" in client.out
        cmd = re.search(r"MYCMD=(.*)!", str(client.out)).group(1)
        cmd = cmd + ".exe"
        static_runtime = True if runtime == "static" else False
        check_vs_runtime(cmd, client, "17", build_type="Release", static_runtime=static_runtime)

    @pytest.mark.tool_visual_studio(version="17")
    @pytest.mark.parametrize("generator", ["Ninja", "NMake Makefiles"])
    def test_clang_cmake_ninja_nmake(self, client, generator):
        client.run("create . pkg/0.1@ -pr=clang -s compiler.runtime=dynamic "
                   "-s compiler.runtime_version=v143 "
                   '-c tools.cmake.cmaketoolchain:generator="{}"'.format(generator))
        assert 'cmake -G "{}"'.format(generator) in client.out
        assert "main __clang_major__12" in client.out
        # Check this! Clang compiler in Windows is reporting MSC_VER and MSVC_LANG!
        assert "main _MSC_VER193" in client.out
        assert "main _MSVC_LANG2014" in client.out
        cmd = re.search(r"MYCMD=(.*)!", str(client.out)).group(1)
        cmd = cmd + ".exe"
        check_vs_runtime(cmd, client, "17", build_type="Release", static_runtime=False)

    @pytest.mark.tool_visual_studio(version="16")
    @pytest.mark.parametrize("generator", ["Ninja", "NMake Makefiles"])
    def test_clang_cmake_runtime_version(self, client, generator):
        client.run("create . pkg/0.1@ -pr=clang -s compiler.runtime=dynamic -s compiler.cppstd=17 "
                   "-s compiler.runtime_version=v142 "
                   '-c tools.cmake.cmaketoolchain:generator="{}"'.format(generator))
        assert 'cmake -G "{}"'.format(generator) in client.out
        assert "main __clang_major__12" in client.out
        # Check this! Clang compiler in Windows is reporting MSC_VER and MSVC_LANG!
        assert "main _MSC_VER192" in client.out
        assert "main _MSVC_LANG2017" in client.out
        cmd = re.search(r"MYCMD=(.*)!", str(client.out)).group(1)
        cmd = cmd + ".exe"
        check_vs_runtime(cmd, client, "16", build_type="Release", static_runtime=False)


@pytest.mark.tool_cmake
@pytest.mark.tool_mingw64_clang
@pytest.mark.skipif(platform.system() != "Windows", reason="requires Win")
def test_clang_mingw(client):
    """ compiling with the clang INSIDE mingw, which uses the
    MinGW runtime, not the MSVC one
    """
    client.run("create . pkg/0.1@ -pr=clang")
    # clang compilations in Windows will use MinGW Makefiles by default
    assert 'cmake -G "MinGW Makefiles"' in client.out
    assert "main __clang_major__13" in client.out
    assert "main _GLIBCXX_USE_CXX11_ABI 1" in client.out
    assert "main __cplusplus2014" in client.out
    assert "main __GNUC__" in client.out
    assert "main __MINGW32__1" in client.out
    assert "main __MINGW64__1" in client.out
    assert "main _MSC_" not in client.out
    assert "main _MSVC_" not in client.out


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
