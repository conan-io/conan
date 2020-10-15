import os
import textwrap

from conans.client.tools import environment_append
from ._base import BaseShimsTestCase


class CMakeCallingTestCase(BaseShimsTestCase):
    def setUp(self):
        self.t.save({'conanfile.py': textwrap.dedent("""
            from conans import ConanFile, CMake

            class Recipe(ConanFile):
                build_requires = 'runner1/version', 'runner2/version'
                generators = 'cmake'
                exports_sources = "*"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
            """)})
        self.t.save({'CMakeLists.txt': textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8.12)
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            project(consumer CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            exec_program(runner1 OUTPUT_VARIABLE RUNNER_OUTPUT)
            message(">>> runner1 output: ${RUNNER_OUTPUT}<<<")

            exec_program(runner2 OUTPUT_VARIABLE RUNNER_OUTPUT)
            message(">>> runner2 output: ${RUNNER_OUTPUT}<<<")

            add_executable(consumer main.cpp)
            add_custom_command(TARGET consumer
                               PRE_BUILD
                               COMMAND runner1
                               COMMENT "Running runner1")
            add_custom_command(TARGET consumer
                               POST_BUILD
                               COMMAND runner2
                               COMMENT "Running runner2")

            """)})
        self.t.save({'main.cpp': textwrap.dedent("""
            int main() { return 0; }
        """)})

    def test_cmake_calling(self):
        self.t.run('create . consumer/version@ --profile:host=default --profile:build=default')
        self.assertIn(textwrap.dedent("""
            >>> runner1 output: library-version: version1
            library-envvar: runner1-value<<<
            """), self.t.out)
        self.assertIn(textwrap.dedent("""
            >>> runner2 output: library-version: version1
            library-envvar: runner2-value<<<
            """), self.t.out)

        self.assertIn(textwrap.dedent("""
            Running runner1
            library-version: version1
            library-envvar: runner1-value
            """), self.t.out)
        self.assertIn(textwrap.dedent("""
            Running runner2
            library-version: version1
            library-envvar: runner2-value
            """), self.t.out)
