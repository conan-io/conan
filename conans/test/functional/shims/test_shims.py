import os
import textwrap
import unittest

from jinja2 import Template

from conans.test.utils.tools import TestClient, GenConanfile


class ShimsTestCase(unittest.TestCase):
    # Files related to a recipe for a library
    lib_cpp = textwrap.dedent("""
        #include "library.h"
        #include <iostream>
        #include <cstdlib>

        void message() {
            std::cout << "library-version: " << LIBRARY_VERSION << "\\n";
            const char* env_variable = std::getenv("LIBRARY_ENVVAR");
            std::cout << "library-envvar: " << env_variable << "\\n";
        }
    """)

    lib_h = textwrap.dedent("""
        #pragma once

        void message();
    """)

    lib_conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake

        class Recipe(ConanFile):
            name = 'library'
            options = {'shared': [True, False]}
            default_options = {'shared': True}
            generators = 'cmake'
            exports_sources = "*"

            def build(self):
                cmake = CMake(self)
                cmake.definitions['LIBRARY_VERSION'] = self.version
                cmake.configure()
                cmake.build()
                cmake.install()

            def package_info(self):
                self.cpp_info.libs = ['library']
                self.env_info.LIBRARY_ENVVAR = self.version
    """)

    lib_cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8.12)
        project(library CXX)

        include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
        conan_basic_setup()

        set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS ON)
        add_library(${PROJECT_NAME} library.cpp)
        set_target_properties(${PROJECT_NAME} PROPERTIES PUBLIC_HEADER library.h)
        target_compile_definitions(${PROJECT_NAME} PRIVATE LIBRARY_VERSION="${LIBRARY_VERSION}")
        install(TARGETS ${PROJECT_NAME}
            RUNTIME DESTINATION bin
            LIBRARY DESTINATION lib
            ARCHIVE DESTINATION lib
            PUBLIC_HEADER DESTINATION include)
    """)

    # Files and recipe for two build-requires that will consume previous library:
    main_cpp = textwrap.dedent("""
        #include "library.h"

        int main() {
            message();
        }
    """)

    main_cmakelist = Template(textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8.12)
        project({{ project }} CXX)

        include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
        conan_basic_setup(TARGETS)

        add_executable(${PROJECT_NAME} main.cpp)
        target_link_libraries(${PROJECT_NAME} CONAN_PKG::library)
        install(TARGETS ${PROJECT_NAME} RUNTIME DESTINATION bin)
    """))

    main_conanfile = Template(textwrap.dedent("""
        from conans import ConanFile, CMake

        class Recipe(ConanFile):
            name = '{{ project }}'
            requires = 'library/{{ lib_version }}'
            exports = "*"
            generators = 'cmake'

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                cmake.install()

            def package_info(self):
                self.cpp_info.exes = ["{{ project }}"]
                #self.env_info.PATH = [os.path.join(self.package_folder, "bin")]
    """))

    def test_shims(self):
        t = TestClient(
            current_folder='/private/var/folders/fc/6mvcrc952dqcjfhl4c7c11ph0000gn/T/tmpijey5_kuconans/path with spaces')
        t.run("config set log.print_run_commands=1")
        # Create two versions for the library
        t.save({
            'lib/library.cpp': self.lib_cpp,
            'lib/library.h': self.lib_h,
            'lib/CMakeLists.txt': self.lib_cmakelists,
            'lib/conanfile.py': self.lib_conanfile,
        })
        t.run('create lib/conanfile.py library/version1@')
        t.run('create lib/conanfile.py library/version2@')

        # Create Runner1 executable using library/version1
        t.save(path=os.path.join(t.current_folder, 'runner1'), files={
            'main.cpp': self.main_cpp,
            'CMakeLists.txt': self.main_cmakelist.render(project='runner1'),
            'conanfile.py': self.main_conanfile.render(project='runner1', lib_version='version1')
        })
        t.run('create runner1/conanfile.py runner1/version@')

        # Create Runner2 executable using library/version2
        t.save(path=os.path.join(t.current_folder, 'runner2'), files={
            'main.cpp': self.main_cpp,
            'CMakeLists.txt': self.main_cmakelist.render(project='runner2'),
            'conanfile.py': self.main_conanfile.render(project='runner2', lib_version='version2')
        })
        t.run('create runner2/conanfile.py runner2/version@')

        # Create a recipe to consume everything provided by the previous recipes
        t.save({'conanfile.py': textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                requires = 'library/version1'
                build_requires = 'runner1/version' #, 'runner2/version'
                generators = 'cmake'

                def build(self):
                    self.output.info("Execute runner1:")
                    self.run("runner1")
                    #self.output.info("Execute runner2:")
                    #self.run("runner2")
            """)})
        t.run('create . consumer/version@ --profile:host=default --profile:build=default')
        #t.run('install . consumer/version@ --profile:host=default --profile:build=default')


        print(t.out)
        self.fail("AAA")

    zlib = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "zlib"

            def package_info(self):
                self.cpp_info.filter_empty = False
    """)

    build_requires = textwrap.dedent("""
        import os
        import stat
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "cmake"
            requires = "zlib/1.0"
            settings = "os"

            def build(self):
                filename = "cmake.cmd" if self.settings.os == "Windows" else "cmake"
                with open(filename, "w") as f:
                    if self.settings.os == "Windows":
                        f.write("@echo on\\n")
                    else:
                        f.write("set -e\\n")
                        f.write("set -x\\n")

                    f.write("echo MY CMAKE!!!\\n")
                    if self.settings.os == "Windows":
                        f.write("echo arguments: %*\\n")
                    else:
                        f.write("echo arguments: $@\\n")

                self.output.info(open(filename).read())

                st = os.stat(filename)
                os.chmod(filename, st.st_mode | stat.S_IEXEC)

            def package(self):
                self.copy("cmake", dst="bin")
                self.copy("cmake.cmd", dst="bin")

            def package_info(self):
                self.cpp_info.exes = ["cmake"]
                #self.env_info.PATH = [os.path.join(self.package_folder, "bin")]
    """)

    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Application(ConanFile):
            name = "app"
            requires = "zlib/1.0"
            build_requires = "cmake/1.0"

            def build(self):
                self.run("cmake --version")
    """)

    def test_basic(self):
        t = TestClient()
        t.save({'zlib.py': self.zlib,
                'cmake.py': self.build_requires,
                'app.py': self.conanfile})
        t.run("create zlib.py zlib/1.0@ --profile=default")
        t.run("create cmake.py cmake/1.0@ --profile=default")
        t.run("create app.py app/1.0@ --profile:host=default --profile:build=default")
        self.assertIn("MY CMAKE!!!", t.out)
        self.assertIn("arguments: --version", t.out)
