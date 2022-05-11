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

    void {name}(){{
        {call}
        #ifdef NDEBUG
        std::cout << "{name}/1.0: Hello World Release!";
        #else
        std::cout << "{name}/1.0: Hello World Debug!";
        #endif
    }}
    """)

cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(myproject CXX)

    find_package(tcp REQUIRED CONFIG)

    add_library(core src/core.cpp include/core.h)
    add_library(client src/client.cpp include/client.h)
    add_library(server src/server.cpp include/server.h)

    target_include_directories(core PUBLIC include)
    target_include_directories(client PUBLIC include)
    target_include_directories(server PUBLIC include)

    set_target_properties(core PROPERTIES PUBLIC_HEADER "include/core.h")
    set_target_properties(client PROPERTIES PUBLIC_HEADER "include/client.h")
    set_target_properties(server PROPERTIES PUBLIC_HEADER "include/server.h")

    target_link_libraries(client core tcp::tcp)
    target_link_libraries(server core tcp::tcp)

    install(TARGETS core client server)
    """)

conanfile_py = textwrap.dedent("""
    import os

    from conan import ConanFile
    from conan.tools.cmake import CMake, cmake_layout


    class LibConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        exports_sources = "CMakeLists.txt", "src/*", "include/*"
        {requires}
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
        {package_info}
    """)


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_cmake
@pytest.mark.tool_xcodebuild
def test_xcodedeps_components():
    client = TestClient(path_with_spaces=False)

    client.run("new tcp/1.0 -m=cmake_lib")
    client.run("create . -tf=None")

    network_pi = """
    def package_info(self):
        self.cpp_info.components["core"].libs = ["core"]
        self.cpp_info.components["core"].includedirs.append("include")
        self.cpp_info.components["core"].libdirs.append("lib")

        self.cpp_info.components["client"].libs = ["client"]
        self.cpp_info.components["client"].includedirs.append("include")
        self.cpp_info.components["client"].libdirs.append("lib")
        self.cpp_info.components["client"].requires.extend(["core", "tcp::tcp"])

        self.cpp_info.components["server"].libs = ["server"]
        self.cpp_info.components["server"].includedirs.append("include")
        self.cpp_info.components["server"].libdirs.append("lib")
        self.cpp_info.components["server"].requires.extend(["core", "tcp::tcp"])
    """

    client.save({
        "include/core.h": header.format(name="core"),
        "include/server.h": header.format(name="server"),
        "include/client.h": header.format(name="client"),
        "src/core.cpp": source.format(name="core", include="", call=""),
        "src/server.cpp": source.format(name="server", include='#include "core.h"\n#include "tcp.h"', call="core(); tcp();"),
        "src/client.cpp": source.format(name="client", include='#include "core.h"\n#include "tcp.h"', call="core(); tcp();"),
        "conanfile.py": conanfile_py.format(requires='requires= "tcp/1.0"', package_info=network_pi),
        "CMakeLists.txt": cmakelists,
    }, clean_first=True)

    client.run("create . network/1.0@")

    chat_pi = """
    def package_info(self):
        self.cpp_info.libs = ["chat"]
        self.cpp_info.includedirs.append("include")
        self.cpp_info.libdirs.append("lib")
        self.cpp_info.requires.append("network::client")
    """

    cmakelists_chat = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(chat CXX)
        find_package(network REQUIRED CONFIG)
        add_library(chat src/chat.cpp include/chat.h)
        target_include_directories(chat PUBLIC include)
        set_target_properties(chat PROPERTIES PUBLIC_HEADER "include/chat.h")
        target_link_libraries(chat network::client)
        install(TARGETS chat)
        """)

    client.save({
        "include/chat.h": header.format(name="chat"),
        "src/chat.cpp": source.format(name="chat", include='#include "client.h"', call="chat();client();"),
        "conanfile.py": conanfile_py.format(requires='requires= "network/1.0"', package_info=chat_pi),
        "CMakeLists.txt": cmakelists_chat,
    }, clean_first=True)

    client.run("create . chat/1.0@")

    xcode_project = textwrap.dedent("""
        name: ChatApp

        options:
          createIntermediateGroups: true
          usesTabs: false
          indentWidth: 4
          tabWidth: 4
          deploymentTarget:
            macOS: "11.3"

        settings:
          CLANG_CXX_LANGUAGE_STANDARD: c++17
          CLANG_CXX_LIBRARY: libc++
          GCC_C_LANGUAGE_STANDARD: c11
          CLANG_WARN_DOCUMENTATION_COMMENTS: false

        fileGroups:
          - conan

        configFiles:
          Debug: conan/conan_config.xcconfig
          Release: conan/conan_config.xcconfig

        targets:
          ChatApp:
            type: application
            platform: macOS
            info:
              path: Generated/Info.plist
            sources:
              - src
            configFiles:
              Debug: conan/conan_config.xcconfig
              Release: conan/conan_config.xcconfig
        """)

    client.save({
        "src/main.cpp": '#include "chat.h"\nint main(){chat();return 0;}',
        "project.yml": xcode_project
    }, clean_first=True)

    client.run("install chat/1.0@ -g XcodeDeps --install-folder=conan")
    client.run("install chat/1.0@ -g XcodeDeps --install-folder=conan -s build_type=Debug --build=missing")
    client.run_command("xcodegen generate")
    client.run_command("xcodebuild -project ChatApp.xcodeproj -configuration Release -arch x86_64 -alltargets")
    client.run_command("xcodebuild -project ChatApp.xcodeproj -configuration Debug -arch x86_64 -alltargets")
