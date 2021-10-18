import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_cmake(version="3.19")
def test_xcodedeps_check_configurations():
    client = TestClient()

    main = textwrap.dedent("""
    #include <iostream>
    int main(int argc, char *argv[]) {
        #ifdef NDEBUG
        std::cout << "Hello World Release!" << std::endl;
        #else
        std::cout << "Hello World Debug!" << std::endl;
        #endif
    }
    """)

    cmakelists = textwrap.dedent("""
    cmake_minimum_required (VERSION 3.1)
    project (cmakehello)
    add_executable (hello main.cpp)
    """)

    client.save({"main.cpp": main, "CMakeLists.txt": cmakelists})

    client.run_command("cmake . -G Xcode")
    client.run_command("xcodebuild -project cmakehello.xcodeproj -configuration Debug")
    client.run_command("./Debug/hello")
    assert "Hello World Debug!" in client.out
    client.run_command("xcodebuild -project cmakehello.xcodeproj -configuration Release")
    client.run_command("./Release/hello")
    assert "Hello World Release!" in client.out
