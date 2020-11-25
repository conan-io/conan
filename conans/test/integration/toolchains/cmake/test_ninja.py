import textwrap
import unittest
import platform

from conan.tools.microsoft.visual import vcvars_command
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient
from conans.client.tools import which


class CMakeNinjaTestCase(unittest.TestCase):
    # This test assumes that 'CMake' and 'Ninja' are available in the system

    main_cpp = gen_function_cpp(name="main")
    cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8.12)
        project(App CXX)
        if(CMAKE_VERSION VERSION_LESS "3.15")
            include(${CMAKE_BINARY_DIR}/conan_project_include.cmake)
        endif()
        set(CMAKE_VERBOSE_MAKEFILE ON)
        add_executable(App main.cpp)
        install(TARGETS App RUNTIME DESTINATION bin)
        """)
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain

        class Foobar(ConanFile):
            name = "foobar"
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = "CMakeLists.txt", "main.cpp"

            def generate(self):
                tc = CMakeToolchain(self, generator="Ninja")
                tc.generate()

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.install()
        """)

    @classmethod
    def setUpClass(cls):
        if not which("ninja"):
            raise unittest.SkipTest("Ninja expected in PATH")

    @unittest.skip("Not tested yet")
    def test_locally_build_linux(self):
        """ Ninja build must proceed using default profile and cmake build (Linux)
        """
        self.client.save({"linux_host": textwrap.dedent("""
            [settings]
            os=Linux
            arch=x86_64
            compiler=gcc
            compiler.version=10
            compiler.libcxx=libstdc++11
            build_type=Release
            """)})
        self._build_locally("linux_host")
        self.client.run_command("objdump -f libfoobar.a")
        self.assertIn("architecture: i386:x86-64", self.client.out)

        self._build_locally("linux_host", "Debug", True)
        self.client.run_command("objdump -f libfoobard.so")
        self.assertIn("architecture: i386:x86-64", self.client.out)
        self.assertIn("DYNAMIC", self.client.out)
        self.client.run_command("file libfoobard.so")
        # FIXME: Broken assert
        #  self.assertIn("with debug_info", self.client.out)

    @unittest.skip("FIXME: Broken on Windows")
    def test_locally_build_Windows(self):
        """ Ninja build must proceed using default profile and cmake build (Windows)
        """
        win_host = textwrap.dedent("""[settings]
                                 os=Windows
                                 arch=x86_64
                                 compiler=Visual Studio
                                 compiler.version=16
                                 compiler.runtime=MD
                                 build_type=Release
                                 [env]
                                 CONAN_CMAKE_GENERATOR=Ninja""")
        self.client.save({"win_host": win_host})
        self._build_locally("win_host")
        self.client.run_command("DUMPBIN /NOLOGO /DIRECTIVES foobar.lib")
        self.assertIn("RuntimeLibrary=MD_Dynamic", self.client.out)
        self.client.run_command("DUMPBIN /NOLOGO /HEADERS foobar.lib")
        self.assertIn("machine (x64)", self.client.out)

        win_host.replace("MD", "MDd")
        self.client.save({"win_host": win_host})
        self._build_locally("win_host", "Debug", False)
        self.client.run_command("DUMPBIN /NOLOGO /DIRECTIVES foobard.lib")
        self.assertIn("RuntimeLibrary=MDd_DynamicDebug", self.client.out)
        self.client.run_command("DUMPBIN /NOLOGO /HEADERS foobard.lib")
        self.assertIn("machine (x64)", self.client.out)

        win_host.replace("MD", "MDd")
        self.client.save({"win_host": win_host})
        self._build_locally("win_host", "Debug", True)
        self.client.run_command("DUMPBIN /NOLOGO /HEADERS foobard.dll")
        self.assertIn("machine (x64)", self.client.out)
        # TODO - How to detect Runtime library from a DLL (command line)?
        # self.client.run_command("DUMPBIN /NOLOGO /DIRECTIVES foobard.dll")
        # self.assertIn("RuntimeLibrary=MDd_DynamicDebug", self.client.out)

    @unittest.skipIf(platform.system() != "Darwin", "Only OSX")
    def test_locally_build_macos(self):
        """ Ninja build must proceed using default profile and cmake build (MacOS)
        """

        self.client.save({"mac_host": textwrap.dedent("""
                          [settings]
                          os=Macos
                          arch=x86_64
                          compiler=apple-clang
                          compiler.version=12.0
                          compiler.libcxx=libc++
                          build_type=Release
                          [env]
                          CONAN_CMAKE_GENERATOR=Ninja""")})
        self._build_locally("mac_host")
        self.client.run_command("lipo -info libfoobar.a")
        self.assertIn("architecture: x86_64", self.client.out)

        self._build_locally("mac_host", "Debug", True)
        self.client.run_command("file libfoobard.dylib")
        self.assertIn("64-bit dynamically linked shared library x86_64", self.client.out)

    def test_devflow_build(self):
        """ Ninja build must proceed using default profile and conan development flow
        """
        client = TestClient(path_with_spaces=False)
        client.save({"conanfile.py": self.conanfile,
                     "main.cpp": self.main_cpp,
                     "CMakeLists.txt": self.cmake})
        win_host = textwrap.dedent("""
            [settings]
            os=Windows
            arch=x86
            compiler=Visual Studio
            compiler.version=15
            compiler.runtime=MTd
            build_type=Debug
             """)
        client.save({"win": win_host})
        client.run("install . -pr=win")
        # Ninja is single-configuration
        # It is necessary to set architecture=x86 here, otherwise final architecture is wrong
        vcvars = vcvars_command("15", architecture="x86")
        client.run("install . -pr=win")
        client.run_command('{} && cmake . -G "Ninja" -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake '
                           .format(vcvars))
        client.run_command("{} && cmake --build .".format(vcvars))
        client.run_command("App")
        self.assertIn("main: Debug!", client.out)
        self.assertIn("main _M_IX86 defined", client.out)
        self.assertIn("main _MSC_VER19", client.out)
        self.assertIn("main _MSVC_LANG2014", client.out)

        client.run_command('{} && dumpbin /dependents /summary /directives "App.exe"'.format(vcvars))
        self.assertIn("KERNEL32.dll", client.out)
        self.assertEqual(1, str(client.out).count(".dll"))
