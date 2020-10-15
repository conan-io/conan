import os
import textwrap
import unittest

from jinja2 import Template

from conans.test.utils.tools import TestClient


class BaseShimsTestCase(unittest.TestCase):
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
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
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
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
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
                # self.env_info.PATH = [os.path.join(self.package_folder, "bin")]
    """))

    @classmethod
    def setUpClass(cls):
        cls.t = TestClient()
        cls.t.run("config set log.print_run_commands=1")
        cls.t.run("config set general.shims_enabled=1")
        # Create two versions for the library
        cls.t.save({
            'lib/library.cpp': cls.lib_cpp,
            'lib/library.h': cls.lib_h,
            'lib/CMakeLists.txt': cls.lib_cmakelists,
            'lib/conanfile.py': cls.lib_conanfile,
        })
        cls.t.run('create lib/conanfile.py library/version1@')
        # t.run('create lib/conanfile.py library/version2@')  # FIXME: Conan v2.0: create and use 'version2'

        # Create Runner1 executable using library/version1
        cls.t.save(path=os.path.join(cls.t.current_folder, 'runner1'), files={
            'main.cpp': cls.main_cpp,
            'CMakeLists.txt': cls.main_cmakelist.render(project='runner1'),
            'conanfile.py': cls.main_conanfile.render(project='runner1', lib_version='version1')
        })
        cls.t.run('create runner1/conanfile.py runner1/version@')

        # Create Runner2 executable using library/version2
        cls.t.save(path=os.path.join(cls.t.current_folder, 'runner2'), files={
            'main.cpp': cls.main_cpp,
            'CMakeLists.txt': cls.main_cmakelist.render(project='runner2'),
            'conanfile.py': cls.main_conanfile.render(project='runner2', lib_version='version1')
            # FIXME: Conan v2.0: use 'library/version2' in the conanfile
        })
        cls.t.run('create runner2/conanfile.py runner2/version@')
