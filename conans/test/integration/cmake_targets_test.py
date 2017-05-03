import os
import unittest
from conans.test.utils.tools import TestClient
from nose.plugins.attrib import attr
import platform

from conans.util.files import load

conanfile_py = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"
    build_policy="missing"
    def package(self):
        self.copy("*", "include")
"""
hello = """
#pragma once
#include <iostream>
void hello(){std::cout<<"Hello World!";}
"""

conanfile = """[requires]
Hello/0.1@lasote/testing
"""

cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup(TARGETS)

add_executable(say_hello main.cpp)
target_link_libraries(say_hello CONAN_PKG::Hello)
"""

main = """
#include "hello.h"
int main(){
    hello();
}
"""


@attr("slow")
class CMakeTargetsTest(unittest.TestCase):

    def header_only_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py,
                     "hello.h": hello})
        client.run("export lasote/testing")
        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake,
                     "main.cpp": main}, clean_first=True)

        client.run('install -g cmake')
        client.runner("cmake .", cwd=client.current_folder)
        self.assertNotIn("WARN: Unknown compiler '", client.user_io.out)
        self.assertNotIn("', skipping the version check...", client.user_io.out)
        self.assertIn("Configuring done", client.user_io.out)
        self.assertIn("Generating done", client.user_io.out)
        self.assertIn("Build files have been written", client.user_io.out)
        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake.replace("conanbuildinfo.cmake",
                                                     "conanbuildinfo_multi.cmake"),
                     "main.cpp": main}, clean_first=True)

        if platform.system() == "Windows":
            debug_install = '-s compiler="Visual Studio" -s compiler.version=14 -s compiler.runtime=MDd'
            release_install = '-s compiler="Visual Studio" -s compiler.version=14 -s compiler.runtime=MD'

            client.run('install %s -s build_type=Debug -g cmake_multi' % debug_install)
            client.run('install %s -s build_type=Release -g cmake_multi' % release_install)
            client.runner("cmake .", cwd=client.current_folder)
            self.assertNotIn("WARN: Unknown compiler '", client.user_io.out)
            self.assertNotIn("', skipping the version check...", client.user_io.out)
            self.assertIn("Configuring done", client.user_io.out)
            self.assertIn("Generating done", client.user_io.out)
            self.assertIn("Build files have been written", client.user_io.out)

    def apple_framework_test(self):

        if platform.system() != "Darwin":
            return


        client = TestClient()
        conanfile_fr = conanfile_py + '''
    def package_info(self):
        self.cpp_info.sharedlinkflags = ["-framework Foundation"]
        self.cpp_info.exelinkflags = self.cpp_info.sharedlinkflags
'''
        client.save({"conanfile.py": conanfile_fr,
                     "hello.h": hello})

        client.run("export lasote/testing")
        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake,
                     "main.cpp": main}, clean_first=True)

        client.run("install -g cmake")
        bili = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("-framework Foundation", bili)
