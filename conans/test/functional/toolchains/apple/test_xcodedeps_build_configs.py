import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_cmake(version="3.19")
def test_xcodedeps_build_configurations():
    client = TestClient()

    client.run("new hello/0.1 -m=cmake_lib")
    client.run("export .")

    main = textwrap.dedent("""
    #include <iostream>
    #include "hello.h"
    int main(int argc, char *argv[]) {
        hello();
        #ifdef NDEBUG
        std::cout << "App Release!" << std::endl;
        #else
        std::cout << "App Debug!" << std::endl;
        #endif
    }
    """)

    cmakelists = textwrap.dedent("""
    cmake_minimum_required (VERSION 3.1)
    project (cmakeapp)
    add_executable (app app.cpp)
    """)

    client.save({"app.cpp": main, "CMakeLists.txt": cmakelists,
                 "conanfile.txt": "[requires]\nhello/0.1\n"}, clean_first=True)

    # we are using cmake here just to generate a Xcode project
    client.run_command("cmake . -G Xcode -T buildsystem=1")

    for config in ["Release", "Debug"]:
        client.run("install . -s build_type={} -s arch=x86_64 -s os.sdk=macosx --build=missing "
                   "-g XcodeDeps".format(config))

    for config in ["Release", "Debug"]:
        client.run_command("xcodebuild -project cmakeapp.xcodeproj -xcconfig conandeps.xcconfig "
                           "-configuration {} -arch x86_64 -sdk=macosx".format(config))
        client.run_command("./{}/app".format(config))
        assert "App {}!".format(config) in client.out
        assert "hello/0.1: Hello World {}!".format(config).format(config) in client.out
