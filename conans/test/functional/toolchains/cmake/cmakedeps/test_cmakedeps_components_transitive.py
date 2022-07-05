import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.tool_cmake
def test_cmakedeps_propagate_components():
    client = TestClient()
    top = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class TopConan(ConanFile):
            name = "top"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "CMakeLists.txt", "src/*", "include/*"
            generators = "CMakeToolchain"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.components["cmp1"].libs = ["cmp1"]
                self.cpp_info.components["cmp2"].libs = ["cmp2"]
        """)

    cmp_cpp = textwrap.dedent("""
        #include <iostream>
        #include "{cmpname}.h"
        void {cmpname}(){{ std::cout << "{cmpname}" << std::endl; }}
        """)

    cmp_include = textwrap.dedent("""
        #pragma once
        void {cmpname}();
        """)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(top CXX)

        add_library(cmp1 src/cmp1.cpp)
        add_library(cmp2 src/cmp2.cpp)

        target_include_directories(cmp1 PUBLIC include)
        target_include_directories(cmp2 PUBLIC include)

        set_target_properties(cmp1 PROPERTIES PUBLIC_HEADER "include/cmp1.h")
        set_target_properties(cmp2 PROPERTIES PUBLIC_HEADER "include/cmp2.h")

        install(TARGETS cmp1)
        install(TARGETS cmp2)
        """)

    client.save({
        'top/conanfile.py': top,
        'top/CMakeLists.txt': cmakelist,
        'top/include/cmp1.h': cmp_include.format(cmpname="cmp1"),
        'top/include/cmp2.h': cmp_include.format(cmpname="cmp2"),
        'top/src/cmp1.cpp': cmp_cpp.format(cmpname="cmp1"),
        'top/src/cmp2.cpp': cmp_cpp.format(cmpname="cmp2"),
    })

    client.run("create top")

    middle = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout


        class MiddleConan(ConanFile):
            name = "middle"
            version = "1.0"
            requires = "top/1.0"
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps", "CMakeToolchain"
            exports_sources = "CMakeLists.txt", "src/*", "include/*"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.requires = ["top::cmp1"]
                self.cpp_info.libs = ["middle"]
        """)

    middle_cpp = textwrap.dedent("""
        #include <iostream>
        #include "cmp1.h"
        #include "middle.h"

        void middle(){ cmp1(); }
        """)

    middle_include = textwrap.dedent("""
        #pragma once
        void middle();
        """)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(middle CXX)
        find_package(top CONFIG REQUIRED COMPONENTS cmp1)
        add_library(middle src/middle.cpp)
        target_include_directories(middle PUBLIC include)
        set_target_properties(middle PROPERTIES PUBLIC_HEADER "include/middle.h")
        target_link_libraries(middle top::cmp1)
        install(TARGETS middle)
        """)

    client.save({
        'middle/conanfile.py': middle,
        'middle/CMakeLists.txt': cmakelist,
        'middle/include/middle.h': middle_include,
        'middle/src/middle.cpp': middle_cpp,
    })

    client.run("create middle")

    consumer = textwrap.dedent("""
        [requires]
        middle/1.0
        [generators]
        CMakeDeps
        CMakeToolchain
    """)

    main = textwrap.dedent("""
        // Use cmp2 that is not required by middle
        #include "cmp2.h"
        int main() { cmp2(); }
        """)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(consumer CXX)
        find_package(middle CONFIG REQUIRED)
        add_executable(consumer main.cpp)
        target_link_libraries(consumer top::cmp2)
        install(TARGETS consumer)
        """)

    client.save({
        'consumer/conanfile.txt': consumer,
        'consumer/CMakeLists.txt': cmakelist,
        'consumer/main.cpp': main,
    })

    with client.chdir("consumer/build"):
        client.run("install ..")
        client.run_command(
            "cmake .. -DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake -DCMAKE_BUILD_TYPE=Release")
        client.run_command("cmake --build .")
        client.run_command("./consumer")
        assert not "cmp2" in client.out
