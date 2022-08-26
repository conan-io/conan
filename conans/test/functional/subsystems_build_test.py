import platform
import tempfile

import pytest
import textwrap

from conans.client.tools import environment_append
from conans.test.assets.autotools import gen_makefile
from conans.test.assets.sources import gen_function_cpp
from conans.test.functional.utils import check_exe_run, check_vs_runtime
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Tests Windows Subsystems")
class TestSubsystems:

    @pytest.mark.tool_msys2
    def test_msys2_available(self):
        """
        Msys2 needs to be installed:
        - Go to https://www.msys2.org/, download the exe installer and run it
        - Follow instructions in https://www.msys2.org/ to update the package DB
        - Install msys2 autotools "pacman -S autotools"
        - Make sure the entry in conftest_user.py of msys2 points to the right location
        """
        client = TestClient()
        client.run_command('uname')
        assert "MSYS" in client.out

    @pytest.mark.tool_cygwin
    def test_cygwin_available(self):
        """ Cygwin is necessary
        - Install from https://www.cygwin.com/install.html, use the default packages
        - Install automake 1.16, gcc-g++, make and binutils packages (will add autoconf and more)
        - Make sure that the path in conftest_user.py is pointing to cygwin "bin" folder
        """
        client = TestClient()
        client.run_command('uname')
        assert "CYGWIN" in client.out

    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw32
    def test_mingw32_available(self):
        """ Mingw32 needs to be installed. We use msys2, don't know if others work
        - Inside msys2, install pacman -S mingw-w64-i686-toolchain (all pkgs)
        """
        client = TestClient()
        client.run_command('uname')
        assert "MINGW32_NT" in client.out

    @pytest.mark.tool_msys2
    @pytest.mark.tool_ucrt64
    def test_ucrt64_available(self):
        """ ucrt64 needs to be installed. We use msys2, don't know if others work
        - Inside msys2, install pacman -S mingw-w64-ucrt-x86_64-toolchain (all pkgs)
        """
        client = TestClient()
        client.run_command('uname')
        assert "MINGW64_NT" in client.out

    @pytest.mark.tool_msys2
    @pytest.mark.tool_msys2_clang64
    def test_clang64_available(self):
        client = TestClient()
        client.run_command('uname')
        assert "MINGW64_NT" in client.out

    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw64
    def test_mingw64_available(self):
        """ Mingw64 needs to be installed. We use msys2, don't know if others work
        - Inside msys2, install pacman -S mingw-w64-x86_64-toolchain (all pkgs)
        """
        client = TestClient()
        client.run_command('uname')
        assert "MINGW64_NT" in client.out

    def test_tool_not_available(self):
        client = TestClient()
        client.run_command('uname', assert_error=True)
        assert "'uname' is not recognized as an internal or external command" in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Tests Windows Subsystems")
class TestSubsystemsBuild:

    @staticmethod
    def _build(client, static_runtime=None, make="make"):
        makefile = gen_makefile(apps=["app"], static_runtime=static_runtime)
        main_cpp = gen_function_cpp(name="main")
        client.save({"Makefile": makefile,
                     "app.cpp": main_cpp})
        client.run_command(make)
        client.run_command("app")

    @pytest.mark.parametrize("static", [True, False])
    @pytest.mark.tool_msys2
    def test_msys2(self, static):
        """
        native MSYS environment, binaries depend on MSYS runtime (msys-2.0.dll)
        Install:
        - pacman -S gcc
        posix-compatible, intended to be run only in MSYS environment (not in pure Windows)
        """
        client = TestClient()
        self._build(client, static_runtime=static)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="msys2")
        assert "_M_X64" not in client.out
        # TODO: Do not hardcode the visual version
        check_vs_runtime("app.exe", client, "15", "Debug", static_runtime=static,
                         subsystem="msys2")

    @pytest.mark.parametrize("static", [True, False])
    @pytest.mark.tool_mingw
    def test_mingw(self, static):
        """
        This will work if you installed the Mingw toolchain outside msys2, from
        https://sourceforge.net/projects/mingw/, and installed gcc, autotools, mingw32-make, etc

        But this doesn't contain "make", only "mingw32-make"
        """
        client = TestClient()
        self._build(client, static_runtime=static, make="mingw32-make")

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86", None, subsystem="mingw32")
        check_vs_runtime("app.exe", client, "15", "Debug", static_runtime=static,
                         subsystem="mingw64")

    @pytest.mark.parametrize("static", [True, False])
    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw64
    def test_mingw64(self, static):
        """
        This will work if you installed the Mingw toolchain inside msys2 as TestSubystems above
        64-bit GCC, binaries
        """
        client = TestClient()
        # pacman -S mingw-w64-x86_64-gcc
        self._build(client, static_runtime=static)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="mingw64")
        # it also defines the VS 64 bits macro
        assert "main _M_X64 defined" in client.out
        check_vs_runtime("app.exe", client, "15", "Debug", static_runtime=static,
                         subsystem="mingw64")

    @pytest.mark.parametrize("static", [True, False])
    @pytest.mark.tool_msys2
    @pytest.mark.tool_msys2_clang64
    def test_msys2_clang64(self, static):
        """
        in msys2
        $ pacman -S mingw-w64-x86_64-clang (NO, this is the mingw variant in ming64)
        $ pacman -S mingw-w64-clang-x86_64-toolchain
        """
        client = TestClient()
        self._build(client, static_runtime=static)

        check_exe_run(client.out, "main", "clang", None, "Debug", "x86_64", None,
                      subsystem="mingw64")
        # it also defines the VS 64 bits macro
        assert "main _M_X64 defined" in client.out
        check_vs_runtime("app.exe", client, "15", "Debug", static_runtime=static,
                         subsystem="clang64")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_msys2_mingw64_clang64
    def test_msys2_mingw64_clang64(self):
        """
        in msys2
        $ pacman -S mingw-w64-x86_64-clang
        $ pacman -S mingw-w64-clang-x86_64-toolchain (NO, this is the clang)
        """
        client = TestClient()
        static = False  # This variant needs --static-glibc -static-libstdc++ (weird) to link static
        # Need to redefine CXX otherwise is gcc
        with environment_append({"CXX": "clang++"}):
            self._build(client, static_runtime=static)

        check_exe_run(client.out, "main", "clang", None, "Debug", "x86_64", None,
                      subsystem="mingw64")
        # it also defines the VS 64 bits macro
        assert "main _M_X64 defined" in client.out
        check_vs_runtime("app.exe", client, "15", "Debug", static_runtime=static,
                         subsystem="mingw64")

    @pytest.mark.parametrize("static", [True, False])
    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw32
    def test_mingw32(self, static):
        """
        This will work if you installed the Mingw toolchain inside msys2 as TestSubystems above
        32-bit GCC, binaries for generic Windows (no dependency on MSYS runtime)
        """
        client = TestClient()
        # pacman -S mingw-w64-i686-gcc
        self._build(client, static_runtime=static)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86", None, subsystem="mingw32")
        # It also defines the VS flag
        assert "main _M_IX86 defined" in client.out
        check_vs_runtime("app.exe", client, "15", "Debug", static_runtime=static,
                         subsystem="mingw32")

    @pytest.mark.parametrize("static", [True, False])
    @pytest.mark.tool_msys2
    @pytest.mark.tool_ucrt64
    def test_ucrt64(self, static):
        """
        This will work if you installed the Mingw toolchain inside msys2 as TestSubystems above
        """
        client = TestClient()

        self._build(client, static_runtime=static)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="mingw32")
        # it also defines the VS macro
        assert "main _M_X64 defined" in client.out
        check_vs_runtime("app.exe", client, "15", "Debug", static_runtime=static,
                         subsystem="ucrt64")

    @pytest.mark.parametrize("static", [True, False])
    @pytest.mark.tool_cygwin
    def test_cygwin(self, static):
        """
        Cygwin environment, binaries depend on Cygwin runtime (cygwin1.dll)
        posix-compatible, intended to be run only in Cygwin environment (not in pure Windows)
        """
        client = TestClient()
        self._build(client, static_runtime=static)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="cygwin")
        check_vs_runtime("app.exe", client, "15", "Debug", static_runtime=static,
                         subsystem="cygwin")


@pytest.mark.skipif(platform.system() != "Windows", reason="Tests Windows Subsystems")
class TestSubsystemsAutotoolsBuild:
    configure_ac = textwrap.dedent("""
        AC_INIT([Tutorial Program], 1.0)
        AM_INIT_AUTOMAKE([foreign])
        AC_PROG_CXX
        AC_CONFIG_FILES(Makefile)
        AC_OUTPUT
        """)  # newline is important

    makefile_am = textwrap.dedent("""
        bin_PROGRAMS = app
        app_SOURCES = main.cpp
        """)

    def _build(self, client):
        main_cpp = gen_function_cpp(name="main")
        client.save({"configure.ac": self.configure_ac,
                     "Makefile.am": self.makefile_am,
                     "main.cpp": main_cpp})

        path = client.current_folder  # Seems unix_path not necessary for this to pass
        client.run_command('bash -lc "cd \\"%s\\" && autoreconf -fiv"' % path)
        client.run_command('bash -lc "cd \\"%s\\" && ./configure"' % path)
        client.run_command("make")
        client.run_command("app")

    @pytest.mark.tool_msys2
    def test_msys(self):
        """
        native MSYS environment, binaries depend on MSYS runtime (msys-2.0.dll)
        posix-compatible, intended to be run only in MSYS environment (not in pure Windows)
        """
        client = TestClient()
        # pacman -S gcc
        self._build(client)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="msys2")
        check_vs_runtime("app.exe", client, "15", "Debug", subsystem="msys2")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw64
    def test_mingw64(self):
        """
        64-bit GCC, binaries for generic Windows (no dependency on MSYS runtime)
        """
        client = TestClient()
        # pacman -S mingw-w64-x86_64-gcc
        self._build(client)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="mingw64")
        check_vs_runtime("app.exe", client, "15", "Debug", subsystem="mingw64")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw32
    def test_mingw32(self):
        """
        32-bit GCC, binaries for generic Windows (no dependency on MSYS runtime)
        """
        client = TestClient()
        # pacman -S mingw-w64-i686-gcc
        self._build(client)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86", None, subsystem="mingw32")
        check_vs_runtime("app.exe", client, "15", "Debug", subsystem="mingw32")

    @pytest.mark.tool_cygwin
    def test_cygwin(self):
        """
        Cygwin environment, binaries depend on Cygwin runtime (cygwin1.dll)
        posix-compatible, intended to be run only in Cygwin environment (not in pure Windows)
        # install autotools, autoconf, libtool, "gcc-c++" and "make" packages
        """
        client = TestClient()
        self._build(client)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="cygwin")
        check_vs_runtime("app.exe", client, "15", "Debug", subsystem="cygwin")


@pytest.mark.skipif(platform.system() != "Windows", reason="Tests Windows Subsystems")
class TestSubsystemsCMakeBuild:
    """ These tests are running the CMake INSIDE THE subsystem, not the Windows native one
    The results are basically the same if CMake is outside the subsystem, but it is NOT
    enough to define CMAKE_CXX_COMPILER full path to the compiler, but it must be in the path

    """
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(app CXX)
        message(STATUS "MYCMAKE VERSION=${CMAKE_VERSION}")
        add_executable(app main.cpp)
        """)

    def _build(self, client, generator="Unix Makefiles", compiler=None, toolset=None):
        main_cpp = gen_function_cpp(name="main")
        client.save({"CMakeLists.txt": self.cmakelists,
                     "main.cpp": main_cpp})

        cmake_compiler = ""
        if compiler:
            cmake_compiler += " -DCMAKE_C_COMPILER={}".format(compiler)
            compilerpp = "clang++" if compiler == "clang" else "g++"
            cmake_compiler += " -DCMAKE_CXX_COMPILER={}".format(compilerpp)
            cmake_compiler += " -DCMAKE_RC_COMPILER={}".format(compiler)
        toolset = "-T {}".format(toolset) if toolset else ""
        client.run_command("cmake {} {}"
                           " -DCMAKE_SH=\"CMAKE_SH-NOTFOUND\" -G \"{}\" .".format(cmake_compiler,
                                                                                  toolset,
                                                                                  generator))
        build_out = client.out
        client.run_command("cmake --build .")
        app = "app" if "Visual" not in generator else r"Debug\app"
        client.run_command(app)
        return build_out

    @pytest.mark.tool_msys2
    def test_msys(self):
        """
        pacman -S cmake
        """
        client = TestClient()
        self._build(client)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="msys2")
        check_vs_runtime("app.exe", client, "15", "Debug", subsystem="msys2")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw64
    def test_mingw64(self):
        """
        $ pacman -S mingw-w64-x86_64-cmake
        """
        client = TestClient()
        self._build(client, generator="MinGW Makefiles")
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="mingw64")
        check_vs_runtime("app.exe", client, "15", "Debug", subsystem="mingw64")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_msys2_clang64
    @pytest.mark.skip(reason="This doesn't work, seems CMake issue")
    def test_msys2_clang64(self):
        """
        FAILS WITH:
        System is unknown to cmake, create:
        Platform/MINGW64_NT-10.0-19044 to use this system,
        """
        client = TestClient()
        self._build(client, generator="Unix Makefiles")
        check_exe_run(client.out, "main", "clang", None, "Debug", "x86_64", None,
                      subsystem="mingw64")
        check_vs_runtime("app.exe", client, "15", "Debug", subsystem="clang64")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_msys2_clang64
    @pytest.mark.tool_cmake(version="3.19")
    def test_msys2_clang64_external(self):
        """
        Exactly the same as the previous tests, but with a native cmake 3.19 (higher priority)
        """
        client = TestClient()
        build_out = self._build(client)
        assert "MYCMAKE VERSION=3.19" in build_out
        check_exe_run(client.out, "main", "clang", None, "Debug", "x86_64", None,
                      subsystem="mingw64")
        check_vs_runtime("app.exe", client, "15", "Debug", subsystem="clang64")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_msys2_mingw64_clang64
    def test_msys2_mingw64_clang64(self):
        """
        """
        client = TestClient()
        # IMPORTANT: Need to redefine the CXX, otherwise CMake will use GCC by default
        with environment_append({"CXX": "clang++"}):
            self._build(client, generator="MinGW Makefiles")
        check_exe_run(client.out, "main", "clang", None, "Debug", "x86_64", None,
                      subsystem="mingw64")
        check_vs_runtime("app.exe", client, "15", "Debug", subsystem="mingw64")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw32
    def test_mingw32(self):
        """
        $ pacman -S mingw-w64-i686-cmake
        """
        client = TestClient()
        self._build(client, generator="MinGW Makefiles")
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86", None, subsystem="mingw32")
        check_vs_runtime("app.exe", client, "15", "Debug", subsystem="mingw32")

    @pytest.mark.tool_cygwin
    def test_cygwin(self):
        """
        Needs to install cmake from the cygwin setup.exe
        """
        client = TestClient()
        # install "gcc-c++" and "make" packages
        self._build(client)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="cygwin")
        check_vs_runtime("app.exe", client, "15", "Debug", subsystem="cygwin")

    @pytest.mark.tool_clang
    def test_clang(self):
        """
        native, LLVM/Clang compiler
        Installing the binary from LLVM site
        https://github.com/llvm/llvm-project/releases/tag/llvmorg-14.0.6
        """
        client = TestClient()
        self._build(client, generator="Ninja", compiler="clang")
        check_exe_run(client.out, "main", "clang", None, "Debug", "x86_64", None, subsystem=None)
        check_vs_runtime("app.exe", client, "15", "Debug", subsystem=None)

    @pytest.mark.tool_cmake(version="3.23")
    @pytest.mark.tool_visual_studio(version="17")
    def test_vs_clang(self):
        """
        native, LLVM/Clang compiler installed with VS 2022 -T ClangCL
        """
        # IMPORTANT: VS CLang not found if in another unit
        folder = tempfile.mkdtemp(suffix='conans')
        client = TestClient(current_folder=folder)
        self._build(client, generator="Visual Studio 17 2022", toolset="ClangCL")
        check_exe_run(client.out, "main", "clang", None, "Debug", "x86_64", None, subsystem=None)
        check_vs_runtime("Debug/app.exe", client, "15", "Debug", subsystem=None)
