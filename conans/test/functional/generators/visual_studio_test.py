# coding=utf-8

import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.test.utils.tools import TestClient
from conans.test.utils.visual_project_files import get_vs_project_files


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


@attr('slow')
@unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
class VisualStudioTest(unittest.TestCase):

    def build_vs_project_with_a_test(self):
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
        old = '<Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />'
        new = old + '<Import Project="{props}" />'.format(props=props)
        files["MyProject/MyProject.vcxproj"] = files["MyProject/MyProject.vcxproj"].replace(old, new)
        client.save(files, clean_first=True)
        client.run("install .")
        client.run("build .")
        client.run_command("x64\Release\MyProject.exe")
        self.assertIn("Hello world!!!", client.out)
