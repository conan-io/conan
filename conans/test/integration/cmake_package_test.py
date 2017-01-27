import unittest
from conans.test.tools import TestClient
from nose.plugins.attrib import attr
import platform

conanfile_py = """
from conans import ConanFile, CMake

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"
    generators = "cmake"
    build_policy="missing"
    settings = "os", "compiler", "arch"
    generators = "cmake"
 
    def build(self):
        cmake = CMake(self.settings)
        prefix = "-DCMAKE_INSTALL_PREFIX='%s'" % self.package_folder
        self.run('cmake . %s %s' % (cmake.command_line, prefix))
        self.run("cmake --build . %s --target install" % cmake.build_config)

    def package(self):
        pass

    def package_info(self):
        self.cpp_info.package = {
            "name": "MyHello",
            "components": ""
        }

"""

# Need custom hello_cmake to ensure correct export of files
hello_cmake = """
PROJECT(MyHello)
include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()
cmake_minimum_required(VERSION 3.1)

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/bin)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_CURRENT_SOURCE_DIR}/bin)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_CURRENT_SOURCE_DIR}/bin)

set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})
    
add_library(hello STATIC hello.cpp)
target_include_directories(hello PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}> $<INSTALL_INTERFACE:include>)

install(TARGETS hello EXPORT Hello RUNTIME DESTINATION bin ARCHIVE DESTINATION lib LIBRARY DESTINATION lib)
install(DIRECTORY . DESTINATION include FILES_MATCHING PATTERN "*.h")
install(FILES "Hello-config.cmake" DESTINATION lib/hello)
install(EXPORT Hello NAMESPACE "MyHello::" DESTINATION lib/hello)
"""

hello_config = """
get_filename_component(SELF_DIR "${CMAKE_CURRENT_LIST_FILE}" PATH)
include(${SELF_DIR}/Hello.cmake)
"""

hello_cpp = """
#pragma once
#include <iostream>
void hello(){std::cout<<"Hello World!";}
"""

hello_h = """
#pragma once
void hello();
"""

say_hello_conanfile = """[requires]
Hello/0.1@dschiffner/testing
"""

say_hello_cmake = """
project(MyHello)
cmake_minimum_required(VERSION 2.8.12)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup(TARGETS)

add_executable(say_hello main.cpp)
target_link_libraries(say_hello Hello::hello)
"""

say_hello_main = """
#include "hello.h"
int main(){
    hello();
}
"""


@attr("slow")
class CMakePackageTest(unittest.TestCase):

    def find_package_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py,
                     "hello.h": hello_h,
                     "hello.cpp": hello_cpp,
                     "CMakeLists.txt": hello_cmake,
                     "Hello-config.cmake": hello_config})
        client.run("export dschiffner/testing")
        client.save({"conanfile.txt": say_hello_conanfile,
                     "CMakeLists.txt": say_hello_cmake,
                     "main.cpp": say_hello_main}, clean_first=True)
        # Install using cmake generator
        client.run('install -g cmake')
        client.runner("cmake .", cwd=client.current_folder)
        self.assertIn("Configuring done", client.user_io.out)
        self.assertIn("Generating done", client.user_io.out)
        self.assertIn("Build files have been written", client.user_io.out)
