import unittest

import pytest

from conans.test.assets.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient

conanfile = """
import os
from conans import ConanFile, tools, CMake

class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"
    exports = "*"
    generators = "cmake"
    settings = "os", "compiler", "arch", "build_type"

    def build(self):
        cmake = CMake(self)
        enable_testing = "Test1" in self.deps_cpp_info.deps
        cmake.configure(defs={"ENABLE_TESTING": enable_testing})
        cmake.build()
        if enable_testing:
            cmake.test()
"""

cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(PackageTest CXX)
cmake_minimum_required(VERSION 2.8.12)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()
if(ENABLE_TESTING)
    add_executable(example test.cpp)
    target_link_libraries(example ${CONAN_LIBS})

    enable_testing()
    add_test(NAME example
              WORKING_DIRECTORY ${CMAKE_BINARY_DIR}/bin
              COMMAND example)
endif()
"""

test_profile = """
include(default)
[build_requires]
Test1/0.1@lasote/stable
"""

test = """#include "helloTest1.h"

int main(){
    helloTest1();
}
"""


@pytest.mark.slow
@pytest.mark.tool_cmake
class BuildRequiresTest(unittest.TestCase):

    def test_test_framework(self):
        client = TestClient()
        files = cpp_hello_conan_files("Test0", with_exe=False)
        client.save(files, clean_first=True)
        client.run("export . lasote/stable")
        files = cpp_hello_conan_files("Test1", deps=["Test0/0.1@lasote/stable"], with_exe=False)
        client.save(files, clean_first=True)
        client.run("export . lasote/stable")
        # client.run("install Test1/0.1@lasote/stable --build=missing")

        client.save({"conanfile.py": conanfile,
                     "test.cpp": test,
                     "CMakeLists.txt": cmake,
                     "profile.txt": test_profile}, clean_first=True)
        client.run("export . lasote/stable")
        client.run("install MyLib/0.1@lasote/stable --build=missing")
        self.assertIn("MyLib/0.1@lasote/stable: Generating the package", client.out)
        self.assertNotIn("100% tests passed", client.out)
        self.assertNotIn("Test0/0.1@lasote/stable", client.out)
        self.assertNotIn("Test1/0.1@lasote/stable", client.out)

        client.run("install MyLib/0.1@lasote/stable -pr=./profile.txt --build")
        self.assertIn("MyLib/0.1@lasote/stable: Generating the package", client.out)
        self.assertIn("Test0/0.1@lasote/stable", client.out)
        self.assertIn("Test1/0.1@lasote/stable", client.out)
        self.assertIn("100% tests passed", client.out)
