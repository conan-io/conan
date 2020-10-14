import os
import textwrap
import unittest

from jinja2 import Template

from conans.test.utils.tools import TestClient


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
                self.env_info.LIBRARY_ENVVAR = 'library-{}'.format(self.version)
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
                self.env_info.LIBRARY_ENVVAR = '{{ project }}-value'
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
            'conanfile.py': self.main_conanfile.render(project='runner2', lib_version='version1')
        })
        t.run('create runner2/conanfile.py runner2/version@')

        # Create a recipe to consume everything provided by the previous recipes
        t.save({'conanfile.py': textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                build_requires = 'runner1/version', 'runner2/version'
                generators = 'cmake'

                def build(self):
                    self.output.info("Execute runner1:")
                    self.run("runner1")
                    self.output.info("Execute runner2:")
                    self.run("runner2")
            """)})
        t.run('create . consumer/version@ --profile:host=default --profile:build=default')
        self.assertIn(textwrap.dedent("""
            ----Running------
            > runner1
            -----------------
            Calling runner1 wrapper
            library-version: version1
            library-envvar: runner1-value
            """), t.out)
        self.assertIn(textwrap.dedent("""
            ----Running------
            > runner2
            -----------------
            Calling runner2 wrapper
            library-version: version1
            library-envvar: runner2-value
            """), t.out)
