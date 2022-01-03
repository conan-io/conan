# coding=utf-8

import os
import platform
import textwrap
import unittest

import pytest

from conans.test.utils.tools import TestClient
from conans.test.assets.visual_project_files import get_vs_project_files

main_cpp = r"""#include <hello.h>
int main(){
    hello();
}
"""

conanfile_txt = r"""[requires]
Hello1/0.1@lasote/testing
[generators]
{generator}
"""


class VisualStudioTest(unittest.TestCase):

    @pytest.mark.slow
    @pytest.mark.tool_cmake
    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
    def test_build_vs_project_with_a(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake
            class HelloConan(ConanFile):
                settings = "os", "build_type", "compiler", "arch"
                exports = '*'
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include")
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.libs = ["hello.a"]
            """)
        hello_cpp = textwrap.dedent("""
            #include <iostream>
            #include "hello.h"
            void hello(){
                std::cout << "Hello world!!!" << std::endl;
            }""")
        hello_h = "void hello();"
        cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8.12)
            project(MyLib CXX)

            set(CMAKE_STATIC_LIBRARY_SUFFIX ".a")
            add_library(hello hello.cpp)
            """)

        client.save({"conanfile.py": conanfile,
                     "CMakeLists.txt": cmake,
                     "hello.cpp": hello_cpp,
                     "hello.h": hello_h})
        client.run("create . mydep/0.1@lasote/testing")

        consumer = textwrap.dedent("""
            from conans import ConanFile, MSBuild
            import os
            class HelloConan(ConanFile):
                settings = "os", "build_type", "compiler", "arch"
                requires = "mydep/0.1@lasote/testing"
                generators = "visual_studio"
                def build(self):
                    msbuild = MSBuild(self)
                    msbuild.build("MyProject.sln")

            """)
        files = get_vs_project_files()
        files["MyProject/main.cpp"] = main_cpp
        files["conanfile.py"] = consumer
        props = os.path.join(client.current_folder, "conanbuildinfo.props")
        old = r'<Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />'
        new = old + '<Import Project="{props}" />'.format(props=props)
        files["MyProject/MyProject.vcxproj"] = files["MyProject/MyProject.vcxproj"].replace(old, new)
        client.save(files, clean_first=True)
        client.run("install .")
        client.run("build .")
        client.run_command(r"x64\Release\MyProject.exe")
        self.assertIn("Hello world!!!", client.out)

    def test_system_libs(self):
        mylib = textwrap.dedent("""
            import os
            from conans import ConanFile

            class MyLib(ConanFile):
                settings = "os", "compiler", "arch", "build_type"

                def package_info(self):
                    self.cpp_info.system_libs = ["sys1"]
                    self.cpp_info.libs = ["lib1"]
                """)
        consumer = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Consumer(ConanFile):
                name = "Consumer"
                version = "0.1"

                requires = "mylib/1.0@us/ch"
                generators = "visual_studio"
                """)
        client = TestClient()
        client.save({"conanfile_mylib.py": mylib, "conanfile_consumer.py": consumer})
        client.run("create conanfile_mylib.py mylib/1.0@us/ch")
        client.run("install conanfile_consumer.py")

        content = client.load("conanbuildinfo.props")
        self.assertIn("<ConanPackageName>Consumer</ConanPackageName>", content)
        self.assertIn("<ConanPackageVersion>0.1</ConanPackageVersion>", content)
        self.assertIn("<ConanLibraries>lib1.lib;</ConanLibraries>", content)
        self.assertIn("<ConanSystemDeps>sys1.lib;</ConanSystemDeps>", content)
        self.assertIn("<AdditionalLibraryDirectories>$(ConanLibraryDirectories)"
                      "%(AdditionalLibraryDirectories)</AdditionalLibraryDirectories>", content)
        self.assertIn("<AdditionalDependencies>$(ConanLibraries)%(AdditionalDependencies)"
                      "</AdditionalDependencies>", content)
        self.assertIn("<AdditionalDependencies>$(ConanSystemDeps)%(AdditionalDependencies)"
                      "</AdditionalDependencies>", content)
