import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
def test_cmake_file_name_spirv_tools():
    """
    Test a simple example imitating the spirv-tools library (cmake_file_name).
    """
    c = TestClient()

    # --- spirv-headers: header-only dependency (like real spirv-headers) ---
    spirv_headers = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import copy

        class SpirvHeadersConan(ConanFile):
            name = "spirv-headers"
            version = "1.0"
            package_type = "header-library"
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = "include/*"

            def package(self):
                copy(self, "*", src=os.path.join(self.source_folder, "include"),
                     dst=os.path.join(self.package_folder, "include"))

            def package_info(self):
                self.cpp_info.components["spirv-headers"].includedirs = ["include"]
    """)

    spirv_header_h = textwrap.dedent("""
        #pragma once
        namespace spv {
            int get_version();
        }
    """)

    # --- spirv-tools: multiple components split via cmake_file_name ---
    spirv_tools_conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake, CMakeToolchain, cmake_layout

        class SpirvToolsConan(ConanFile):
            name = "spirv-tools"
            version = "1.0"
            package_type = "library"
            settings = "os", "arch", "compiler", "build_type"
            options = {"shared": [True, False]}
            default_options = {"shared": False}
            requires = "spirv-headers/1.0"
            generators = "CMakeConfigDeps", "CMakeToolchain"
            exports_sources = "src/*", "include/*", "CMakeLists.txt"

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
                # Split into separate config files per CMake package name
                self.cpp_info.set_property("cmake_file_name", {
                    "SPIRV-Tools": {"components": ["spirv-tools-core"]},
                    "SPIRV-Tools-opt": {"components": ["spirv-tools-opt"]},
                    "SPIRV-Tools-link": {"components": ["spirv-tools-link"]},
                })

                lib_ext = "lib" if self.settings.os == "Windows" else "a"
                lib_prefix = "" if self.settings.os == "Windows" else "lib"

                # spirv-tools-core
                self.cpp_info.components["spirv-tools-core"].set_property("cmake_target_name", "SPIRV-Tools")
                self.cpp_info.components["spirv-tools-core"].libs = ["SPIRV-Tools"]
                self.cpp_info.components["spirv-tools-core"].type = "static-library"
                self.cpp_info.components["spirv-tools-core"].includedirs = ["include"]
                self.cpp_info.components["spirv-tools-core"].location = os.path.join("lib", f"{lib_prefix}SPIRV-Tools.{lib_ext}")
                self.cpp_info.components["spirv-tools-core"].requires = ["spirv-headers::spirv-headers"]

                # spirv-tools-opt
                self.cpp_info.components["spirv-tools-opt"].set_property("cmake_target_name", "SPIRV-Tools-opt")
                self.cpp_info.components["spirv-tools-opt"].libs = ["SPIRV-Tools-opt"]
                self.cpp_info.components["spirv-tools-opt"].type = "static-library"
                self.cpp_info.components["spirv-tools-opt"].includedirs = ["include"]
                self.cpp_info.components["spirv-tools-opt"].location = os.path.join("lib", f"{lib_prefix}SPIRV-Tools-opt.{lib_ext}")
                self.cpp_info.components["spirv-tools-opt"].requires = ["spirv-tools-core", "spirv-headers::spirv-headers"]

                # spirv-tools-link
                self.cpp_info.components["spirv-tools-link"].set_property("cmake_target_name", "SPIRV-Tools-link")
                self.cpp_info.components["spirv-tools-link"].libs = ["SPIRV-Tools-link"]
                self.cpp_info.components["spirv-tools-link"].type = "static-library"
                self.cpp_info.components["spirv-tools-link"].includedirs = ["include"]
                self.cpp_info.components["spirv-tools-link"].location = os.path.join("lib", f"{lib_prefix}SPIRV-Tools-link.{lib_ext}")
                self.cpp_info.components["spirv-tools-link"].requires = ["spirv-tools-core", "spirv-tools-opt"]
    """)

    # Minimal C++ sources
    core_cpp = textwrap.dedent("""
        #include "spirv_tools/core.h"
        #include "spirv/header.h"
        namespace spv { int get_version() { return 100; } }
        int spirv_tools_core_version() { return spv::get_version(); }
    """)
    opt_cpp = textwrap.dedent("""
        #include "spirv_tools/opt.h"
        #include "spirv_tools/core.h"
        int spirv_tools_opt_optimize() { return spirv_tools_core_version() + 1; }
    """)
    link_cpp = textwrap.dedent("""
        #include "spirv_tools/link.h"
        #include "spirv_tools/opt.h"
        int spirv_tools_link() { return spirv_tools_opt_optimize() + 1; }
    """)

    core_h = textwrap.dedent("""
        #pragma once
        int spirv_tools_core_version();
    """)
    opt_h = textwrap.dedent("""
        #pragma once
        int spirv_tools_opt_optimize();
    """)
    link_h = textwrap.dedent("""
        #pragma once
        int spirv_tools_link();
    """)

    spirv_tools_cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(spirv-tools CXX)

        find_package(spirv-headers REQUIRED)

        add_library(SPIRV-Tools STATIC src/core.cpp)
        target_include_directories(SPIRV-Tools PUBLIC include)
        target_link_libraries(SPIRV-Tools PUBLIC spirv-headers::spirv-headers)

        add_library(SPIRV-Tools-opt STATIC src/opt.cpp)
        target_include_directories(SPIRV-Tools-opt PUBLIC include)
        target_link_libraries(SPIRV-Tools-opt PUBLIC SPIRV-Tools)

        add_library(SPIRV-Tools-link STATIC src/link.cpp)
        target_include_directories(SPIRV-Tools-link PUBLIC include)
        target_link_libraries(SPIRV-Tools-link PUBLIC SPIRV-Tools SPIRV-Tools-opt)

        install(TARGETS SPIRV-Tools SPIRV-Tools-opt SPIRV-Tools-link
                RUNTIME DESTINATION bin
                LIBRARY DESTINATION lib
                ARCHIVE DESTINATION lib)
        install(DIRECTORY include/ DESTINATION include)
    """)

    # --- Save spirv-headers ---
    c.save({
        "spirv-headers/conanfile.py": spirv_headers,
        "spirv-headers/include/spirv/header.h": spirv_header_h,
    })
    c.run("create spirv-headers")

    # --- Save spirv-tools ---
    c.save({
        "spirv-tools/conanfile.py": spirv_tools_conanfile,
        "spirv-tools/CMakeLists.txt": spirv_tools_cmake,
        "spirv-tools/src/core.cpp": core_cpp,
        "spirv-tools/src/opt.cpp": opt_cpp,
        "spirv-tools/src/link.cpp": link_cpp,
        "spirv-tools/include/spirv_tools/core.h": core_h,
        "spirv-tools/include/spirv_tools/opt.h": opt_h,
        "spirv-tools/include/spirv_tools/link.h": link_h,
    }, clean_first=True)

    c.run("create spirv-tools")

    # --- Verify generated config files ---
    c.run("install --requires=spirv-tools/1.0 -g CMakeConfigDeps")
    assert c.load("SPIRV-ToolsConfig.cmake")
    assert c.load("SPIRV-Tools-optConfig.cmake")
    assert c.load("SPIRV-Tools-linkConfig.cmake")
    paths = c.load("conan_cmakedeps_paths.cmake")
    assert "set(SPIRV-Tools_DIR" in paths
    assert "set(SPIRV-Tools-opt_DIR" in paths
    assert "set(SPIRV-Tools-link_DIR" in paths

    # --- Consumer with test_package that builds ---
    consumer_conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class ConsumerConan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "spirv-tools/1.0"
            generators = "CMakeConfigDeps", "CMakeToolchain"
            exports_sources = "src/*", "CMakeLists.txt"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                # Check the result
                self.run(os.path.join(self.cpp.build.bindirs[0], "example"))
    """)

    consumer_cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(example CXX)

        find_package(SPIRV-Tools-link REQUIRED CONFIG)

        add_executable(example src/main.cpp)
        target_link_libraries(example PRIVATE SPIRV-Tools-link)
    """)

    consumer_main = textwrap.dedent("""
        #include <iostream>
        #include "spirv_tools/link.h"
        int main() {
            std::cout << "spirv-tools link result: " << spirv_tools_link() << std::endl;
            return 0;
        }
    """)

    c.save({
        "consumer/conanfile.py": consumer_conanfile,
        "consumer/CMakeLists.txt": consumer_cmake,
        "consumer/src/main.cpp": consumer_main,
    }, clean_first=True)

    c.run("build consumer")
    # Check the output
    assert "spirv-tools link result: 102" in c.out
