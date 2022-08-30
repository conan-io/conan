import os
import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_cmake
def test_xcodedeps_components():
    """
    tcp/1.0 is a lib without components
    network/1.0 lib that requires tcp/1.0 and has three components:
     - core
     - client -> requires core component and tcp::tcp
     - server -> requires core component and tcp::tcp

    chat/1.0 -> lib that requires network::client component

    We create an application called ChatApp that uses XcodeDeps for chat/1.0 dependency
    And check that we are not requiring more than the needed components,
    nothing from network::server for example
    """
    client = TestClient(path_with_spaces=False)

    client.run("new tcp/1.0 -m=cmake_lib")
    client.run("create . -tf=None")

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
            std::cout << "{name}/1.0: Hello World Release!" << std::endl;
            #else
            std::cout << "{name}/1.0: Hello World Debug!" << std::endl;
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
        "src/server.cpp": source.format(name="server", include='#include "core.h"\n#include "tcp.h"',
                                        call="core(); tcp();"),
        "src/client.cpp": source.format(name="client", include='#include "core.h"\n#include "tcp.h"',
                                        call="core(); tcp();"),
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
        "src/chat.cpp": source.format(name="chat", include='#include "client.h"', call="client();"),
        "conanfile.py": conanfile_py.format(requires='requires= "network/1.0"',
                                            package_info=chat_pi),
        "CMakeLists.txt": cmakelists_chat,
    }, clean_first=True)

    client.run("create . chat/1.0@")

    xcode_project = textwrap.dedent("""
        name: ChatApp
        fileGroups:
          - conan
        targets:
          chat:
            type: tool
            platform: macOS
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
    client.run("install chat/1.0@ -g XcodeDeps --install-folder=conan -s build_type=Debug "
               "--build=missing")
    chat_xcconfig = client.load(os.path.join("conan", "conan_chat_chat.xcconfig"))
    assert '#include "conan_network_client.xcconfig"' in chat_xcconfig
    assert '#include "conan_network_server.xcconfig"' not in chat_xcconfig
    assert '#include "conan_network_network.xcconfig"' not in chat_xcconfig
    host_arch = client.get_default_host_profile().settings['arch']
    arch = "arm64" if host_arch == "armv8" else host_arch
    client.run_command("xcodegen generate")
    client.run_command(f"xcodebuild -project ChatApp.xcodeproj -configuration Release -arch {arch}")
    client.run_command(f"xcodebuild -project ChatApp.xcodeproj -configuration Debug -arch {arch}")
    client.run_command("build/Debug/chat")
    assert "core/1.0: Hello World Debug!" in client.out
    assert "tcp/1.0: Hello World Debug!" in client.out
    assert "client/1.0: Hello World Debug!" in client.out
    assert "chat/1.0: Hello World Debug!" in client.out
    client.run_command("build/Release/chat")
    assert "core/1.0: Hello World Release!" in client.out
    assert "tcp/1.0: Hello World Release!" in client.out
    assert "client/1.0: Hello World Release!" in client.out
    assert "chat/1.0: Hello World Release!" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_cmake
def test_xcodedeps_test_require():
    client = TestClient()
    client.run("new gtest/1.0 -m cmake_lib")
    # client.run("new cmake_lib -d name=app -d version=1.0")
    client.run("create . -tf=None")

    # Create library having build and test requires
    conanfile = textwrap.dedent(r'''
        from conan import ConanFile
        class HelloLib(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            def build_requirements(self):
                self.test_requires('gtest/1.0')
        ''')
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("install . -g XcodeDeps")
    host_arch = client.get_default_host_profile().settings['arch']
    arch = "arm64" if host_arch == "armv8" else host_arch
    assert os.path.isfile(os.path.join(client.current_folder, "conan_gtest.xcconfig"))
    assert os.path.isfile(os.path.join(client.current_folder, "conan_gtest_gtest.xcconfig"))
    assert os.path.isfile(os.path.join(client.current_folder,
                                       f"conan_gtest_gtest_release_{arch}.xcconfig"))
    assert '#include "conan_gtest.xcconfig"' in client.load("conandeps.xcconfig")
