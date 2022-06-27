import platform

import pytest
import textwrap

from conans.client.tools import environment_append
from conans.test.assets.autotools import gen_makefile
from conans.test.assets.sources import gen_function_cpp
from conans.test.conftest import tools_locations
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
    def _build(client):
        makefile = gen_makefile(apps=["app"])
        main_cpp = gen_function_cpp(name="main")
        client.save({"Makefile": makefile,
                     "app.cpp": main_cpp})
        client.run_command("make")
        client.run_command("app")

    @pytest.mark.tool_msys2
    def test_msys2(self):
        """
        native MSYS environment, binaries depend on MSYS runtime (msys-2.0.dll)
        Install:
        - pacman -S gcc
        posix-compatible, intended to be run only in MSYS environment (not in pure Windows)
        """
        client = TestClient()
        self._build(client)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="msys2")
        assert "_M_X64" not in client.out
        # TODO: Do not hardcode the visual version
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="msys2")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw64
    def test_mingw64(self):
        """
        This will work if you installed the Mingw toolchain inside msys2 as TestSubystems above
        64-bit GCC, binaries
        """
        client = TestClient()
        # pacman -S mingw-w64-x86_64-gcc
        self._build(client)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="mingw64")
        # it also defines the VS 64 bits macro
        assert "main _M_X64 defined" in client.out
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="mingw64")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_msys2_clang64
    def test_msys2_clang64(self):
        """
        in msys2
        $ pacman -S mingw-w64-x86_64-clang (NO, this is the mingw variant in ming64)
        $ pacman -S mingw-w64-clang-x86_64-toolchain
        """
        client = TestClient()
        self._build(client)

        check_exe_run(client.out, "main", "clang", None, "Debug", "x86_64", None,
                      subsystem="mingw64")
        # it also defines the VS 64 bits macro
        assert "main _M_X64 defined" in client.out
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="clang64")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_msys2_mingw64_clang64
    def test_msys2_mingw64_clang64(self):
        """
        in msys2
        $ pacman -S mingw-w64-x86_64-clang
        $ pacman -S mingw-w64-clang-x86_64-toolchain (NO, this is the clang)
        """
        client = TestClient()
        # Need to redefine CXX otherwise is gcc
        with environment_append({"CXX": "clang++"}):
            self._build(client)

        check_exe_run(client.out, "main", "clang", None, "Debug", "x86_64", None,
                      subsystem="mingw64")
        # it also defines the VS 64 bits macro
        assert "main _M_X64 defined" in client.out
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="mingw64")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw32
    def test_mingw32(self):
        """
        This will work if you installed the Mingw toolchain inside msys2 as TestSubystems above
        32-bit GCC, binaries for generic Windows (no dependency on MSYS runtime)
        """
        client = TestClient()
        # pacman -S mingw-w64-i686-gcc
        self._build(client)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86", None, subsystem="mingw32")
        # It also defines the VS flag
        assert "main _M_IX86 defined" in client.out
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="mingw32")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_ucrt64
    def test_ucrt64(self):
        """
        This will work if you installed the Mingw toolchain inside msys2 as TestSubystems above
        """
        client = TestClient()

        self._build(client)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="mingw32")
        # it also defines the VS macro
        assert "main _M_X64 defined" in client.out
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="ucrt64")

    @pytest.mark.tool_cygwin
    def test_cygwin(self):
        """
        Cygwin environment, binaries depend on Cygwin runtime (cygwin1.dll)
        posix-compatible, intended to be run only in Cygwin environment (not in pure Windows)
        """
        client = TestClient()
        self._build(client)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="cygwin")
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="cygwin")


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
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="msys2")

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
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="mingw64")

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
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="mingw32")

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
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="cygwin")


@pytest.mark.skipif(platform.system() != "Windows", reason="Tests Windows Subsystems")
class TestSubsystemsCMakeBuild:
    """ These tests are running the CMake INSIDE THE subsystem, not the Windows native one
    """
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(app)
        add_executable(app main.cpp)
        """)

    def _build(self, client, generator="Unix Makefiles"):
        main_cpp = gen_function_cpp(name="main")
        client.save({"CMakeLists.txt": self.cmakelists,
                     "main.cpp": main_cpp})

        client.run_command("cmake "
                           " -DCMAKE_C_FLAGS=\"-Wl,-verbose\""
                           " -DCMAKE_CXX_FLAGS=\"-Wl,-verbose\""
                           " -DCMAKE_SH=\"CMAKE_SH-NOTFOUND\" -G \"%s\" ." % generator)
        client.run_command("cmake --build .")
        client.run_command("app")

    @pytest.mark.tool_msys2
    def test_msys(self):
        """
        pacman -S cmake
        """
        client = TestClient()
        self._build(client)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="msys2")
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="msys2")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw64
    def test_mingw64(self):
        """
        $ pacman -S mingw-w64-x86_64-cmake
        """
        client = TestClient()
        self._build(client, generator="MinGW Makefiles")
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="mingw64")
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="mingw64")

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
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="clang64")

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
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="mingw64")

    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw32
    def test_mingw32(self):
        """
        $ pacman -S mingw-w64-i686-cmake
        """
        client = TestClient()
        self._build(client, generator="MinGW Makefiles")
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86", None, subsystem="mingw32")
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="mingw32")

    @pytest.mark.tool_cygwin
    def test_cygwin(self):
        """
        Needs to install cmake from the cygwin setup.exe
        """
        client = TestClient()
        # install "gcc-c++" and "make" packages
        self._build(client)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None, subsystem="cygwin")
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="cygwin")


@pytest.mark.skipif(platform.system() != "Windows", reason="Tests Windows Subsystems")
class TestSubsystemsCMakeExternalBuild:
    """ These tests runs from the Windows native CMake, pointing just to the compilers inside
    the subsystems
    """
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(app CXX)
        add_executable(app main.cpp)
        """)

    def _build(self, client, location, compiler, generator="MinGW Makefiles"):
        """ This seems it wont work with "Unix Makefiles", as now we are in Windows CMake?
        """
        main_cpp = gen_function_cpp(name="main")
        client.save({"CMakeLists.txt": self.cmakelists,
                     "main.cpp": main_cpp})
        client.run_command("cmake --version")
        print(client.out)

        make = "mingw32-make" if "Unix" not in generator else "make"
        compilerpp = "clang++" if compiler == "clang" else "g++"
        client.run_command("cmake "
                           " -DCMAKE_MAKE_PROGRAM={location}/{make}"
                           " -DCMAKE_CXX_COMPILER={location}/{compilerpp}.exe"
                           " -DCMAKE_C_COMPILER={location}/{compiler}.exe"
                           " -DCMAKE_SH=\"CMAKE_SH-NOTFOUND\""
                           " -G \"{generator}\""
                           " .".format(make=make, location=location, compiler=compiler,
                                       compilerpp=compilerpp, generator=generator))
        print(client.out)
        client.run_command("cmake --build .")
        print(client.out)
        # IMPORTANT: This needs the RUNTIME PATH to locate the shared libc++.dll libraries
        with environment_append({}):
            client.run_command("app")
            print(client.out)

    def test_msys2_gcc(self):
        """
        """
        client = TestClient()
        msys2 = tools_locations["msys2"]
        if msys2.get("disabled"):
            pytest.skip("msys2 disabled")
        location = msys2["system"]["path"]["Windows"]
        # Otherwise the msys2 gcc fails to load its own gcc shared libs to compile
        with environment_append({}):
            self._build(client, location, generator="Unix Makefiles", compiler="gcc")
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None,
                      subsystem="msys2")
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="msys2")

    def test_msys2_clang64(self):
        """
        """
        client = TestClient()
        msys2 = tools_locations["msys2_clang64"]
        if msys2.get("disabled"):
            pytest.skip("msys2 disabled")
        location = msys2["system"]["path"]["Windows"]
        self._build(client, location, compiler="clang")
        check_exe_run(client.out, "main", "clang", None, "Debug", "x86_64", None,
                      subsystem="mingw64")
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="clang64")

    def test_msys2_mingw64(self):
        """
        """
        client = TestClient()
        msys2 = tools_locations["mingw64"]
        if msys2.get("disabled"):
            pytest.skip("msys2 disabled")
        location = msys2["system"]["path"]["Windows"]
        cmake = tools_locations["cmake"]
        cmake = cmake["3.19"]["path"]["Windows"]
        with environment_append({"PATH": "{};{}".format(cmake, location)}):
            self._build(client, location=location, generator="MinGW Makefiles", compiler="gcc")
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None,
                      subsystem="mingw64")
        check_vs_runtime("app.exe", client, "15", "Release", subsystem="mingw64")
