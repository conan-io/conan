import platform

import pytest
import textwrap

from conans.test.assets.autotools import gen_makefile
from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.sources import gen_function_cpp
from conans.test.functional.utils import check_exe_run
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Tests Windows Subsystems")
class TestSubsystems:

    @pytest.mark.tool("msys2")
    def test_msys2_available(self):
        client = TestClient()
        client.run_command('uname')
        assert "MSYS" in client.out

    @pytest.mark.tool("cygwin")
    def test_cygwin_available(self):
        client = TestClient()
        client.run_command('uname')
        assert "CYGWIN" in client.out

    @pytest.mark.tool("msys2")
    @pytest.mark.tool("mingw32")
    def test_mingw32_available(self):
        client = TestClient()
        client.run_command('uname')
        assert "MINGW32_NT" in client.out

    @pytest.mark.tool("msys2")
    @pytest.mark.tool("mingw64")
    def test_mingw64_available(self):
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

    @pytest.mark.tool("msys2")
    def test_msys(self):
        """
        native MSYS environment, binaries depend on MSYS runtime (msys-2.0.dll)
        posix-compatible, intended to be run only in MSYS environment (not in pure Windows)
        """
        client = TestClient()
        # pacman -S gcc
        self._build(client)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None)

        assert "__MINGW32__" not in client.out
        assert "__MINGW64__" not in client.out
        assert "__MSYS__" in client.out

    @pytest.mark.tool("msys2")
    @pytest.mark.tool("mingw64")
    def test_mingw64(self):
        """
        64-bit GCC, binaries for generic Windows (no dependency on MSYS runtime)
        """
        client = TestClient()
        # pacman -S mingw-w64-x86_64-gcc
        self._build(client)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None)

        assert "__MINGW64__" in client.out
        assert "__CYGWIN__" not in client.out
        assert "__MSYS__" not in client.out

    @pytest.mark.tool("msys2")
    @pytest.mark.tool("mingw64")
    def test_mingw64_recipe(self):
        """
        A recipe with self.run_bash=True and msys2 configured, using mingw to build stuff with make
        from the subsystem
        """
        client = TestClient()
        makefile = gen_makefile(apps=["app"])
        main_cpp = gen_function_cpp(name="main")
        conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.gnu import Autotools
        from conan.tools.layout import basic_layout
        from conan.tools.files import copy
        class HelloConan(ConanFile):
            exports_sources = "*.cpp", "Makefile"
            generators = "AutotoolsToolchain"
            win_bash = True

            def build(self):
                self.output.warning(self.build_folder)
                auto = Autotools(self)
                auto.make()

            def package(self):
                copy(self, "app*", self.build_folder, os.path.join(self.package_folder, "bin"))

        """)
        test_conanfile = textwrap.dedent("""
                import os
                from conan import ConanFile
                class TestConan(ConanFile):

                    def requirements(self):
                        self.tool_requires(self.tested_reference_str)

                    def test(self):
                        self.run("app")
                """)
        profile = textwrap.dedent("""
        include(default)
        [conf]
        tools.microsoft.bash:subsystem=msys2
        """)
        client.save({"conanfile.py": conanfile,
                     "Makefile": makefile,
                     "app.cpp": main_cpp,
                     "test_package/conanfile.py": test_conanfile,
                     "myprofile": profile})

        client.run("create . --name foo --version 1.0 --profile:build myprofile")
        assert "__MINGW64__" in client.out
        assert "__CYGWIN__" not in client.out

    @pytest.mark.tool("msys2")
    @pytest.mark.tool("mingw32")
    def test_mingw32(self):
        """
        32-bit GCC, binaries for generic Windows (no dependency on MSYS runtime)
        """
        client = TestClient()
        # pacman -S mingw-w64-i686-gcc
        self._build(client)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86", None)

        assert "__MINGW32__" in client.out
        assert "__CYGWIN__" not in client.out
        assert "__MSYS__" not in client.out

    @pytest.mark.tool("cygwin")
    def test_cygwin(self):
        """
        Cygwin environment, binaries depend on Cygwin runtime (cygwin1.dll)
        posix-compatible, intended to be run only in Cygwin environment (not in pure Windows)
        """
        client = TestClient()
        # install "gcc-c++" and "make" packages
        self._build(client)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None)

        assert "__CYGWIN__" in client.out
        assert "__MINGW32__" not in client.out
        assert "__MINGW64__" not in client.out
        assert "__MSYS__" not in client.out


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

    @pytest.mark.tool("msys2")
    def test_msys(self):
        """
        native MSYS environment, binaries depend on MSYS runtime (msys-2.0.dll)
        posix-compatible, intended to be run only in MSYS environment (not in pure Windows)
        """
        client = TestClient()
        # pacman -S gcc
        self._build(client)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None)

        assert "__MINGW32__" not in client.out
        assert "__MINGW64__" not in client.out
        assert "__MSYS__" in client.out

    @pytest.mark.tool("msys2")
    @pytest.mark.tool("mingw64")
    def test_mingw64(self):
        """
        64-bit GCC, binaries for generic Windows (no dependency on MSYS runtime)
        """
        client = TestClient()
        # pacman -S mingw-w64-x86_64-gcc
        self._build(client)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None)

        assert "__MINGW64__" in client.out
        assert "__CYGWIN__" not in client.out
        assert "__MSYS__" not in client.out

    @pytest.mark.tool("msys2")
    @pytest.mark.tool("mingw32")
    def test_mingw32(self):
        """
        32-bit GCC, binaries for generic Windows (no dependency on MSYS runtime)
        """
        client = TestClient()
        # pacman -S mingw-w64-i686-gcc
        self._build(client)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86", None)

        assert "__MINGW32__" in client.out
        assert "__CYGWIN__" not in client.out
        assert "__MSYS__" not in client.out

    @pytest.mark.tool("cygwin")
    def test_cygwin(self):
        """
        Cygwin environment, binaries depend on Cygwin runtime (cygwin1.dll)
        posix-compatible, intended to be run only in Cygwin environment (not in pure Windows)
        """
        client = TestClient()
        # install "gcc-c++" and "make" packages
        self._build(client)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None)

        assert "__CYGWIN__" in client.out
        assert "__MINGW32__" not in client.out
        assert "__MINGW64__" not in client.out
        assert "__MSYS__" not in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Tests Windows Subsystems")
class TestSubsystemsCMakeBuild:
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8)
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

    @pytest.mark.tool("cmake")
    @pytest.mark.tool("msys2")
    def test_msys(self):
        """
        native MSYS environment, binaries depend on MSYS runtime (msys-2.0.dll)
        posix-compatible, intended to be run only in MSYS environment (not in pure Windows)
        """
        client = TestClient()
        # pacman -S gcc
        self._build(client)

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None)

        assert "__MINGW32__" not in client.out
        assert "__MINGW64__" not in client.out
        assert "__MSYS__" in client.out

    @pytest.mark.tool("msys2")
    @pytest.mark.tool("mingw64")
    @pytest.mark.tool("cmake")
    def test_mingw64(self):
        """
        64-bit GCC, binaries for generic Windows (no dependency on MSYS runtime)
        """
        client = TestClient()
        # pacman -S mingw-w64-x86_64-gcc
        self._build(client, generator="MinGW Makefiles")

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None)

        assert "__MINGW64__" in client.out
        assert "__CYGWIN__" not in client.out
        assert "__MSYS__" not in client.out

    @pytest.mark.tool("msys2")
    @pytest.mark.tool("mingw32")
    @pytest.mark.tool("cmake")
    def test_mingw32(self):
        """
        32-bit GCC, binaries for generic Windows (no dependency on MSYS runtime)
        """
        client = TestClient()
        # pacman -S mingw-w64-i686-gcc
        self._build(client, generator="MinGW Makefiles")

        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86", None)

        assert "__MINGW32__" in client.out
        assert "__CYGWIN__" not in client.out
        assert "__MSYS__" not in client.out

    @pytest.mark.tool("cygwin")
    def test_cygwin(self):
        """
        Cygwin environment, binaries depend on Cygwin runtime (cygwin1.dll)
        posix-compatible, intended to be run only in Cygwin environment (not in pure Windows)
        """
        client = TestClient()
        # install "gcc-c++" and "make" packages
        self._build(client)
        check_exe_run(client.out, "main", "gcc", None, "Debug", "x86_64", None)

        assert "__CYGWIN__" in client.out
        assert "__MINGW32__" not in client.out
        assert "__MINGW64__" not in client.out
        assert "__MSYS__" not in client.out
