import platform
import re
import tempfile
import textwrap

import pytest

from conan.test.assets.cmake import gen_cmakelists
from conan.test.assets.sources import gen_function_cpp, gen_function_c
from test.functional.utils import check_vs_runtime, check_exe_run
from conan.test.utils.tools import TestClient


@pytest.fixture
def client():
    # IMPORTANT: This cannot use the default tests location, if in Windows, it can be another unit
    # like F and Visual WONT FIND ClangCL
    t = tempfile.mkdtemp(suffix='conans')
    c = TestClient(cache_folder=t)
    clang_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        build_type=Release
        compiler=clang
        compiler.version=13
        [conf]
        tools.build:compiler_executables={"cpp": "clang++", "c": "clang", "rc": "clang"}
        """)
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
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
                self.run(cmd)

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                cmd = os.path.join(self.package_folder, "bin", "my_app")
                self.output.info("MYCMD={}!".format(os.path.abspath(cmd)))
        """)
    c.save({"conanfile.py": conanfile,
            "clang": clang_profile,
            "CMakeLists.txt": gen_cmakelists(appname="my_app", appsources=["src/main.cpp"],
                                             install=True),
            "src/main.cpp": gen_function_cpp(name="main")})
    return c


@pytest.mark.tool("cmake")
@pytest.mark.tool("clang", "16")
@pytest.mark.skipif(platform.system() != "Windows", reason="requires Win")
class TestLLVMClang:
    """ External LLVM/clang, with different CMake generators
    This links always with the VS runtime, it is built-in
    """

    @pytest.mark.tool("mingw64")
    @pytest.mark.tool("visual_studio", "17")
    @pytest.mark.tool("clang", "16")  # repeated, for priority over the mingw64 clang
    @pytest.mark.parametrize("runtime", ["static", "dynamic"])
    def test_clang_mingw(self, client, runtime):
        """ compiling with an LLVM-clang installed, which uses by default the
        VS runtime
        """
        client.run("create . --name=pkg --version=0.1 -pr=clang "
                   "-s compiler.runtime_version=v143 "
                   "-s compiler.runtime={}".format(runtime))
        # clang compilations in Windows will use MinGW Makefiles by default
        assert 'cmake -G "MinGW Makefiles"' in client.out
        assert "GNU-like command-line" in client.out
        assert "main __clang_major__16" in client.out
        assert "main _MSC_VER193" in client.out
        assert "main _MSVC_LANG2014" in client.out
        assert "main _M_X64 defined" in client.out
        assert "main __x86_64__ defined" in client.out

        check_exe_run(client.out, "main", "clang", None, "Release", "x86_64", "14")
        cmd = re.search(r"MYCMD=(.*)!", str(client.out)).group(1)
        cmd = cmd + ".exe"
        static_runtime = (runtime == "static")
        check_vs_runtime(cmd, client, "17", build_type="Release", static_runtime=static_runtime)

    @pytest.mark.tool("visual_studio", "17")
    @pytest.mark.parametrize("generator", ["Ninja", "NMake Makefiles"])
    def test_clang_cmake_ninja_nmake(self, client, generator):
        client.run("create . --name=pkg --version=0.1 -pr=clang -s compiler.runtime=dynamic "
                   "-s compiler.runtime_version=v143 "
                   '-c tools.cmake.cmaketoolchain:generator="{}"'.format(generator))

        assert 'cmake -G "{}"'.format(generator) in client.out
        assert "GNU-like command-line" in client.out
        assert "main __clang_major__16" in client.out
        assert "main _MSC_VER193" in client.out
        assert "main _MSVC_LANG2014" in client.out
        assert "main _M_X64 defined" in client.out
        assert "main __x86_64__ defined" in client.out
        cmd = re.search(r"MYCMD=(.*)!", str(client.out)).group(1)
        cmd = cmd + ".exe"
        check_vs_runtime(cmd, client, "17", build_type="Release", static_runtime=False)

    @pytest.mark.tool("visual_studio", "16")
    @pytest.mark.tool("clang", "16")  # repeated, for priority over the mingw64 clang
    def test_clang_cmake_runtime_version(self, client):
        generator = "Ninja"
        # Make sure that normal CMakeLists with verify=False works
        client.save({"CMakeLists.txt": gen_cmakelists(verify=False, appname="my_app",
                                                      appsources=["src/main.cpp"], install=True)})
        client.run("create . --name=pkg --version=0.1 -pr=clang -s compiler.runtime=dynamic -s compiler.cppstd=17 "
                   "-s compiler.runtime_version=v142 "
                   '-c tools.cmake.cmaketoolchain:generator="{}"'.format(generator))

        assert 'cmake -G "{}"'.format(generator) in client.out
        assert "GNU-like command-line" in client.out
        assert "main __clang_major__16" in client.out
        # Check this! Clang compiler in Windows is reporting MSC_VER and MSVC_LANG!
        assert "main _MSC_VER192" in client.out
        assert "main _MSVC_LANG2017" in client.out
        assert "main _M_X64 defined" in client.out
        assert "main __x86_64__ defined" in client.out
        cmd = re.search(r"MYCMD=(.*)!", str(client.out)).group(1)
        cmd = cmd + ".exe"
        check_vs_runtime(cmd, client, "16", build_type="Release", static_runtime=False)


@pytest.mark.skipif(platform.system() != "Windows", reason="requires Win")
class TestVSClangCL:
    """
    This is also LLVM/Clang, but distributed with the VS installation
    """
    @pytest.mark.tool("cmake", "3.23")
    @pytest.mark.tool("visual_studio", "17")
    def test_clang_visual_studio_generator(self, client):
        """ This is using the embedded ClangCL compiler, not the external one"""
        generator = "Visual Studio 17"
        client.run("create . --name=pkg --version=0.1 -pr=clang -s compiler.runtime=dynamic "
                   "-s compiler.cppstd=17 -s compiler.runtime_version=v143 "
                   '-c tools.cmake.cmaketoolchain:generator="{}"'.format(generator))
        assert 'cmake -G "{}"'.format(generator) in client.out
        assert "MSVC-like command-line" in client.out
        # My local is 17, but CI ClangCL still 16
        assert "main __clang_major__16" in client.out
        # Check this! Clang compiler in Windows is reporting MSC_VER and MSVC_LANG!
        assert "main _MSC_VER193" in client.out
        assert "main _MSVC_LANG2017" in client.out
        assert "main _M_X64 defined" in client.out
        assert "main __x86_64__ defined" in client.out
        assert "-m64" not in client.out
        cmd = re.search(r"MYCMD=(.*)!", str(client.out)).group(1)
        cmd = cmd + ".exe"
        check_vs_runtime(cmd, client, "17", build_type="Release", static_runtime=False)


@pytest.mark.tool("cmake")
@pytest.mark.skipif(platform.system() != "Windows", reason="requires Win")
class TestMsysClang:
    @pytest.mark.tool("msys2_clang64")
    def test_msys2_clang(self, client):
        """ Using the msys2 clang64 subsystem
        We are not really injecting the msys2 root with make, so using
        MinGW Makefiles
        """
        client.run('create . --name=pkg --version=0.1 -pr=clang -s os.subsystem=msys2 '
                   '-s compiler.libcxx=libc++ '
                   '-c tools.cmake.cmaketoolchain:generator="MinGW Makefiles"')
        # clang compilations in Windows will use MinGW Makefiles by default
        assert 'cmake -G "MinGW Makefiles"' in client.out
        # TODO: Version is still not controlled
        assert "main __clang_major__15" in client.out
        # Not using libstdc++
        assert "_GLIBCXX_USE_CXX11_ABI" not in client.out
        assert "main __cplusplus2014" in client.out
        assert "main __GNUC__" in client.out
        assert "main __MINGW32__1" in client.out
        assert "main __MINGW64__1" in client.out
        assert "main _MSC_" not in client.out
        assert "main _MSVC_" not in client.out
        assert "main _M_X64 defined" in client.out
        assert "main __x86_64__ defined" in client.out

        cmd = re.search(r"MYCMD=(.*)!", str(client.out)).group(1)
        cmd = cmd + ".exe"
        check_vs_runtime(cmd, client, "16", build_type="Release",
                         static_runtime=False, subsystem="clang64")

    @pytest.mark.tool("msys2_mingw64_clang64")
    def test_msys2_clang_mingw(self, client):
        """ compiling with the clang INSIDE mingw, which uses the
        MinGW runtime, not the MSVC one
        For 32 bits, it doesn't seem possible to install the toolchain
        For 64 bits require "pacman -S mingw-w64-x86-clang++"
        """
        # TODO: This should probably go to the ``os.subsystem=ming64" but lets do it in other PR
        client.run('create . --name=pkg --version=0.1 -pr=clang '
                   '-s compiler.libcxx=libstdc++')
        # clang compilations in Windows will use MinGW Makefiles by default
        assert 'cmake -G "MinGW Makefiles"' in client.out
        # TODO: Version is still not controlled
        assert "main __clang_major__15" in client.out
        assert "main _GLIBCXX_USE_CXX11_ABI 0" in client.out
        assert "main __cplusplus2014" in client.out
        assert "main __GNUC__" in client.out
        assert "main __MINGW32__1" in client.out
        assert "main __MINGW64__1" in client.out
        assert "main _MSC_" not in client.out
        assert "main _MSVC_" not in client.out
        assert "main _M_X64 defined" in client.out
        assert "main __x86_64__ defined" in client.out

        cmd = re.search(r"MYCMD=(.*)!", str(client.out)).group(1)
        cmd = cmd + ".exe"
        check_vs_runtime(cmd, client, "16", build_type="Release",
                         static_runtime=False, subsystem="mingw64")

    @pytest.mark.tool("msys2_clang64")
    def test_clang_pure_c(self, client):
        """ compiling with the clang INSIDE mingw, which uses the
        MinGW runtime, not the MSVC one
        For 32 bits, it doesn't seem possible to install the toolchain
        For 64 bits require "pacman -S mingw-w64-x86-clang++"
        """
        client.save({"CMakeLists.txt": gen_cmakelists(verify=False, language="C", appname="my_app",
                                                      appsources=["src/main.c"], install=True),
                     "src/main.c": gen_function_c(name="main")})
        client.run(f"create . --name=pkg --version=0.1 -pr=clang")
        # clang compilations in Windows will use MinGW Makefiles by default
        assert 'cmake -G "MinGW Makefiles"' in client.out
        assert "main __clang_major__15" in client.out
        assert "GLIBCXX" not in client.out
        assert "cplusplus" not in client.out
        assert "main __GNUC__" in client.out
        assert "main __MINGW32__1" in client.out
        assert "main __MINGW64__1" in client.out
        assert "main _MSC_" not in client.out
        assert "main _MSVC_" not in client.out
        assert "main _M_X64 defined" in client.out
        assert "main __x86_64__ defined" in client.out

        cmd = re.search(r"MYCMD=(.*)!", str(client.out)).group(1)
        cmd = cmd + ".exe"
        # static_runtime equivalent to C, for checking, no dep on libc++
        check_vs_runtime(cmd, client, "16", build_type="Release", static_runtime=True,
                         subsystem="clang64")


@pytest.mark.tool("cmake")
@pytest.mark.tool("ninja")
@pytest.mark.tool("clang", "16")
@pytest.mark.skipif(platform.system() != "Windows", reason="requires Win")
def test_error_clang_cmake_ninja_custom_cxx(client):
    clang_profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        build_type=Release
        compiler=clang
        compiler.version=16
        [buildenv]
        CXX=/no/exist/clang++
        """)
    client.save({"clang":     clang_profile})
    client.run("create . --name=pkg --version=0.1 -pr=clang "
               "-c tools.cmake.cmaketoolchain:generator=Ninja", assert_error=True)
    assert 'Could not find compiler' in client.out
    assert '/no/exist/clang++' in client.out
