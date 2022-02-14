import platform
import textwrap

import pytest

from conans.test.functional.toolchains.apple.test_xcodedeps_build_configs import create_xcode_project
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
@pytest.mark.tool_xcodebuild
def test_project_xcodebuild():
    client = TestClient(path_with_spaces=False)

    client.run("new hello/0.1 -m=cmake_lib")
    client.run("export .")

    main = textwrap.dedent("""
        #include <iostream>
        #include "hello.h"
        int main(int argc, char *argv[]) {
            hello();
            #ifndef DEBUG
            std::cout << "App Release!" << std::endl;
            #else
            std::cout << "App Debug!" << std::endl;
            #endif
        }
        """)

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.apple import XcodeBuild
        class MyApplicationConan(ConanFile):
            name = "myapplication"
            version = "1.0"
            requires = "hello/0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "XcodeDeps"
            exports_sources = "app.xcodeproj/*", "app/*"
            def build(self):
                xcode = XcodeBuild(self)
                xcode.build("app.xcodeproj")

            def package(self):
                self.copy("*/app", dst="bin", src=".", keep_path=False)

            def package_info(self):
                self.cpp_info.bindirs = ["bin"]
        """)

    test = textwrap.dedent("""
        import os
        from conans import ConanFile, tools
        class TestApp(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "VirtualRunEnv"
            def test(self):
                if not tools.cross_building(self):
                    self.run("app", env="conanrun")
        """)

    project_name = "app"
    client.save({"conanfile.py": conanfile,
                 "test_package/conanfile.py": test}, clean_first=True)
    create_xcode_project(client, project_name, main)
    client.run("create . --build=missing")
    assert "hello/0.1: Hello World Release!" in client.out
    assert "App Release!" in client.out
    client.run("create . -s build_type=Debug --build=missing")
    assert "hello/0.1: Hello World Debug!" in client.out
    assert "App Debug!" in client.out
