import platform
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
            exports_sources = "CMakeLists.txt", "include/*"
            generators = "CMakeToolchain"

            def layout(self):
                cmake_layout(self)

            def package(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.install()

            def package_info(self):
                self.cpp_info.components["cmp1"].includedirs = ["include"]
                self.cpp_info.components["cmp2"].includedirs = ["include"]
        """)

    cmp_include = textwrap.dedent("""
        #pragma once
        #include <iostream>
        void {cmpname}(){{ std::cout << "{cmpname}" << std::endl; }};
        """)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(top CXX)
        add_library(cmp1 INTERFACE)
        add_library(cmp2 INTERFACE)
        target_include_directories(cmp1 INTERFACE include)
        target_include_directories(cmp2 INTERFACE include)
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
            exports_sources = "CMakeLists.txt", "include/*"

            def layout(self):
                cmake_layout(self)

            def package(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.install()

            def package_info(self):
                self.cpp_info.requires = ["top::cmp1"]
        """)

    middle_include = textwrap.dedent("""
        #pragma once
        #include <iostream>
        #include "cmp1.h"
        void middle(){ cmp1(); };
        """)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(middle CXX)
        find_package(top CONFIG REQUIRED COMPONENTS cmp1)
        add_library(middle INTERFACE)
        target_include_directories(middle INTERFACE include)
        target_link_libraries(middle INTERFACE top::cmp1)
        set_target_properties(middle PROPERTIES PUBLIC_HEADER "include/middle.h")
        install(TARGETS middle)
        """)

    client.save({
        'middle/conanfile.py': middle,
        'middle/CMakeLists.txt': cmakelist,
        'middle/include/middle.h': middle_include,
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

    client.run("install consumer")

    assert "top::cmp2" not in client.load("top-release-x86_64-data.cmake")
    assert "top::cmp2" not in client.load("top-Target-release.cmake")
