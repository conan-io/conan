import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient

header = textwrap.dedent("""
    #pragma once
    void {name}();
    """)

source = textwrap.dedent("""
    #include <iostream>
    #include "{name}.h"
    {include}

    void {name}(){
        {call}
        #ifdef NDEBUG
        std::cout << "{name}/1.0: Hello World Release!\n";
        #else
        std::cout << "{name}/1.0: Hello World Debug!\n";
        #endif
    }
    """)

cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(myproject CXX)

    find_package(tcp REQUIRED CONFIG)

    add_library(core src/core.cpp include/core/core.h)
    add_library(client src/client.cpp include/client/client.h)
    add_library(server src/server.cpp include/server/server.h)

    target_include_directories(core PUBLIC include/core)
    target_include_directories(client PUBLIC include/client)
    target_include_directories(server PUBLIC include/server)

    set_target_properties(core PROPERTIES PUBLIC_HEADER "include/core/core.h")
    set_target_properties(client PROPERTIES PUBLIC_HEADER "include/client/client.h")
    set_target_properties(server PROPERTIES PUBLIC_HEADER "include/server/server.h")

    target_link_libraries(client core tcp::tcp)
    target_link_libraries(server core tcp::tcp)

    install(TARGETS core client server)
    """)

conanfile_py = textwrap.dedent("""
    import os

    from conan import ConanFile
    from conan.tools.cmake import CMake, cmake_layout


    class NetworkLibConan(ConanFile):
        name = "network"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"
        exports_sources = "CMakeLists.txt", "src/*", "include/*"
        requires = "tcp/1.0"
        generators = "CMakeToolchain", "CMakeDeps"

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
            self.cpp_info.components["core"].libs = ["core"]
            self.cpp_info.components["core"].includedirs.append(os.path.join("include", "core"))

            self.cpp_info.components["client"].libs = ["client"]
            self.cpp_info.components["client"].includedirs.append(os.path.join("include", "client"))
            self.cpp_info.components["client"].requires.extend(["core", "tcp::tcp"])

            self.cpp_info.components["server"].libs = ["server"]
            self.cpp_info.components["server"].includedirs.append(os.path.join("include", "server"))
            self.cpp_info.components["server"].requires.extend(["core", "tcp::tcp"])
    """)


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_cmake
@pytest.mark.tool_xcodebuild
def test_xcodedeps_components():
    client = TestClient(path_with_spaces=False)

    client.run("new tcp/1.0 -m=cmake_lib")
    client.run("create . -tf=None")

    client.save({
        "include/core/core.h": header.format(name="core"),
        "include/server/server.h": header.format(name="server"),
        "include/client/client.h": header.format(name="client"),
        "src/core.cpp": header.format(name="core", include="", call=""),
        "src/server.cpp": header.format(name="server", include='#include "core.h"', call="core(); tcp();"),
        "src/client.cpp": header.format(name="client", include='#include "core.h"', call="core(); tcp();"),
        "conanfile.py": conanfile_py,
        "CMakeLists.txt": cmakelists,
    }, clean_first=True)

    client.run("create .")

    client.run("install network/1.0@ -g XcodeDeps")
