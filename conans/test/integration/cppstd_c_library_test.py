# coding=utf-8

import platform
import textwrap
import unittest

from conans.test.utils.tools import TestClient


class CppStdCLibraryTest(unittest.TestCase):
    main_c = textwrap.dedent("""
        #include <stdio.h>

        int main()
        {
            #ifdef __cplusplus
                printf("Hello >>>C++<<<");
            #else
                printf("Hello >>>C<<<");
            #endif
            return 0;
        }
    """)

    base_conanfile = textwrap.dedent("""
        from conans import ConanFile, tools, CMake, Meson, AutoToolsBuildEnvironment, \\
                VisualStudioBuildEnvironment
        from conans.client.generators.compiler_args import CompilerArgsGenerator
        
        class Lib(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
    """)

    def _check_result(self, test_client, generator, path_to_app="./bin/app"):
        test_client.run("install . -g {}".format(generator))
        test_client.run("build .")
        test_client.runner(path_to_app, cwd=test_client.current_folder)
        self.assertIn("Hello >>>C<<<", test_client.out)

    def test_cmake(self):
        conanfile = self.base_conanfile + textwrap.dedent("""                
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
            
            # Using CMake
        """)

        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.6.0)
            project(myproject C)
            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()
            add_executable(app main.c)
        """)

        t = TestClient()
        t.save({"conanfile.py": conanfile,
                "main.c": self.main_c,
                "CMakeLists.txt": cmakelists})

        path_to_app = "bin\\app.exe" if platform.system() == "Windows" else "./bin/app"
        self._check_result(t, "cmake", path_to_app)

    def test_meson(self):
        conanfile = self.base_conanfile + textwrap.dedent("""
                def build(self):
                    meson = Meson(self)
                    meson.configure(build_folder="bin")
                    meson.build()
            # Using Meson
        """)

        meson_build = textwrap.dedent("""
            project('myproject', 'c')
            executable('app', 'main.c')
        """)

        t = TestClient()
        t.save({"conanfile.py": conanfile,
                "main.c": self.main_c,
                "meson.build": meson_build})

        path_to_app = "bin\\app.exe" if platform.system() == "Windows" else "./bin/app"
        self._check_result(t, "txt", path_to_app)

    @unittest.skipUnless(platform.system() == "Linux", "Requires Linux (could be installed in Mac)")
    def test_autotoolsbuildenvironment(self):
        conanfile = self.base_conanfile + textwrap.dedent("""
                def build(self):
                    autotools = AutoToolsBuildEnvironment(self)
                    autotools.configure()
                    autotools.make()
            # Using AutoToolsBuildEnvironment
        """)

        configure_ac = textwrap.dedent("""
            AC_INIT([app], [0.1], [])
            AM_INIT_AUTOMAKE
            AC_PROG_CC
            AC_CONFIG_FILES([Makefile])
            AC_OUTPUT
        """)

        makefile_in = textwrap.dedent("""
            AUTOMAKE_OPTIONS = foreign
            bin_PROGRAMS = app
            app_SOURCES = main.c
        """)

        t = TestClient()
        t.save({"conanfile.py": conanfile,
                "main.c": self.main_c,
                "configure.ac": configure_ac,
                "Makefile.am": makefile_in})
        t.runner("aclocal", cwd=t.current_folder)
        t.runner("autoconf", cwd=t.current_folder)
        t.runner("automake --add-missing", cwd=t.current_folder)
        self._check_result(t, "txt", path_to_app="./app")

    @unittest.skipUnless(platform.system() == "Windows", "Only in Windows")
    def test_visualstudiobuildenvironment(self):
        conanfile = self.base_conanfile + textwrap.dedent("""
                def build(self):
                    env_build = VisualStudioBuildEnvironment(self)
                    with tools.environment_append(env_build.vars):
                        vcvars = tools.vcvars_command(self.settings)
                        self.run('%s && cl /Tc main.c /Fe:app.exe' % vcvars)
            # Using VisualStudioBuildEnvironment
        """)

        t = TestClient()
        t.save({"conanfile.py": conanfile,
                "main.c": self.main_c})
        self._check_result(t, "txt", path_to_app="app.exe")

    @unittest.skipUnless(platform.system() == "Windows", "Only in Windows")
    def test_compiler_args_generator_windows(self):
        conanfile = self.base_conanfile + textwrap.dedent("""
                def build(self):
                    compiler_args = CompilerArgsGenerator(self).content
                    vcvars = tools.vcvars_command(self.settings)
                    command = '%s && cl /Tc main.c /Fe:app.exe {}' % vcvars
                    self.run(command.format(compiler_args))
            # Using CompilerArgsGenerator
        """)

        t = TestClient()
        t.save({"conanfile.py": conanfile,
                "main.c": self.main_c})
        self._check_result(t, "txt", path_to_app="app.exe")

    @unittest.skipIf(platform.system() == "Windows", "Not in Windows")
    def test_compiler_args_generator_not_win(self):
        conanfile = self.base_conanfile + textwrap.dedent("""
                def build(self):
                    compiler_args = CompilerArgsGenerator(self).content
                    if self.settings.compiler == "gcc":
                        command = 'gcc -x c main.c {} -o app'
                    elif self.settings.compiler == "apple-clang":
                        command = 'clang -x c main.c {} -o app'
                    else:
                        raise RuntimeError("Compiler {} unknown".format(self.settings.compiler))
                    self.run(command.format(compiler_args))
            # Using CompilerArgsGenerator
        """)

        t = TestClient()
        t.save({"conanfile.py": conanfile,
                "main.c": self.main_c})
        self._check_result(t, "txt", path_to_app="./app")
