import platform

import pytest
import textwrap

from conans.test.assets.sources import gen_function_cpp
from conans.test.functional.utils import check_exe_run
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Tests Windows Subsystems")
class TestSubsystemsBuild:

    @pytest.fixture
    def client(self):
        return TestClient()

    @pytest.mark.tool_msys2
    def test_msys2_available(self, client):
        client.run_command('uname')
        assert "MSYS" in client.out

    @pytest.mark.tool_cygwin
    def test_cygwin_available(self, client):
        client.run_command('uname')
        assert "CYGWIN" in client.out

    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw32
    def test_mingw32_available(self, client):
        client.run_command('uname')
        assert "MINGW32_NT" in client.out

    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw64
    def test_mingw64_available(self, client):
        client.run_command('uname')
        assert "MINGW64_NT" in client.out

    def test_tool_not_available(self, client):
        client.run_command('uname', assert_error=True)
        assert "'uname' is not recognized as an internal or external command" in client.out

    makefile = textwrap.dedent("""
        .PHONY: all
        all: app

        app: main.o
        	$(CXX) $(CFLAGS) -o app main.o

        main.o: main.cpp
        	$(CXX) $(CFLAGS) -c -o main.o main.cpp
        """)

    def _build(self, client):
        main_cpp = gen_function_cpp(name="main")

        client.save({"Makefile": self.makefile,
                          "main.cpp": main_cpp})

        client.run_command("make")

        client.run_command("app")

    @pytest.mark.tool_msys2
    def test_msys(self, client):
        """
        native MSYS environment, binaries depend on MSYS runtime (msys-2.0.dll)
        posix-compatible, intended to be run only in MSYS environment (not in pure Windows)
        """
        # pacman -S gcc
        self._build(client)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None)

        assert "__MINGW32__" not in client.out
        assert "__MINGW64__" not in client.out
        assert "__MSYS__" in client.out

    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw64
    def test_mingw64(self, client):
        """
        64-bit GCC, binaries for generic Windows (no dependency on MSYS runtime)
        """
        # pacman -S mingw-w64-x86_64-gcc
        self._build(client)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None)

        assert "__MINGW64__" in client.out
        assert "__CYGWIN__" not in client.out
        assert "__MSYS__" not in client.out

    @pytest.mark.tool_msys2
    @pytest.mark.tool_mingw32
    def test_mingw32(self, client):
        """
        32-bit GCC, binaries for generic Windows (no dependency on MSYS runtime)
        """
        # pacman -S mingw-w64-i686-gcc
        self._build(client)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86", None)

        assert "__MINGW32__" in client.out
        assert "__CYGWIN__" not in client.out
        assert "__MSYS__" not in client.out

    @pytest.mark.tool_cygwin
    def test_cygwin(self, client):
        """
        Cygwin environment, binaries depend on Cygwin runtime (cygwin1.dll)
        posix-compatible, intended to be run only in Cygwin environment (not in pure Windows)
        """
        # install "gcc-c++" and "make" packages
        self._build(client)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None)

        assert "__CYGWIN__" in client.out
        assert "__MINGW32__" not in client.out
        assert "__MINGW64__" not in client.out
        assert "__MSYS__" not in client.out
