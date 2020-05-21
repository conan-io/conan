import os
import platform
import textwrap
import unittest

import six
from nose.plugins.attrib import attr

from conans.client.tools import replace_in_file
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID


class CMakeGeneratorsWithComponentsTest(unittest.TestCase):

    def general_test(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class GreetingsConan(ConanFile):
                name = "greetings"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake"
                exports_sources = "src/*"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.lib", dst="lib", keep_path=False)
                    self.copy("*.dll", dst="bin", keep_path=False)
                    self.copy("*.dylib*", dst="lib", keep_path=False)
                    self.copy("*.so", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.names["cmake_find_package"] = "greetings"
                    self.cpp_info.components["hello"].names["cmake_find_package"] = "hello"
                    self.cpp_info.components["hello"].libs = ["hello"]
                    self.cpp_info.components["bye"].names["cmake_find_package"] = "bye"
                    self.cpp_info.components["bye"].libs = ["bye"]
        """)
        hello_h = textwrap.dedent("""
            #pragma once

            void hello(std::string noun);
        """)
        hello_cpp = textwrap.dedent("""
            #include <iostream>
            #include "hello.h"# We need to add our requirements too

            void hello(std::string noun) {
                std::cout << "Hello " << noun << "!" << std::endl;
            }
        """)
        bye_h = textwrap.dedent("""
            #pragma once

            void bye(std::string noun);
        """)
        bye_cpp = textwrap.dedent("""
            #include <iostream>
            #include "bye.h"

            void bye(std::string noun) {
                std::cout << "Bye " << noun << "!" << std::endl;
}
        """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8)
            project(greetings CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()

            add_library(hello hello.cpp)
            add_library(bye bye.cpp)
        """)
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "src/CMakeLists.txt": cmakelists,
                     "src/hello.h": hello_h,
                     "src/hello.cpp": hello_cpp,
                     "src/bye.h": bye_h,
                     "src/bye.cpp": bye_cpp})
        client.run("create .")

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake, tools

            class WorldConan(ConanFile):
                name = "world"
                version = "0.0.1"
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake_find_package"
                exports_sources = "src/*"
                requires = "greetings/0.0.1"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(source_folder="src")
                    cmake.build()

                def package(self):
                    self.copy("*.h", dst="include", src="src")
                    self.copy("*.lib", dst="lib", keep_path=False)
                    self.copy("*.dll", dst="bin", keep_path=False)
                    self.copy("*.dylib*", dst="lib", keep_path=False)
                    self.copy("*.so", dst="lib", keep_path=False)
                    self.copy("*.a", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.names["cmake_find_package"] = "world"
                    self.cpp_info.components["helloworld"].names["cmake_find_package"] = "helloworld"
                    self.cpp_info.components["helloworld"].requires = ["greetings::hello"]
                    self.cpp_info.components["helloworld"].libs = ["helloworld"]
                    self.cpp_info.components["worldall"].names["cmake_find_package"] = "worldall"
                    self.cpp_info.components["worldall"].requires = ["greetings::bye", "helloworld"]
                    self.cpp_info.components["worldall"].libs = ["worldall"]
        """)
        helloworld_h = textwrap.dedent("""
            #pragma once

            void helloWorld();
        """)
        helloworld_cpp = textwrap.dedent("""
            #include <iostream>
            #include "hello.h"
            #include "helloworld.h"

            void helloWorld() {
                hello("World");
            }
        """)
        worldall_h = textwrap.dedent("""
            #pragma once

            void worldAll();
        """)
        worldall_cpp = textwrap.dedent("""
            #include <iostream>
            #include "bye.h"
            #include "helloworld.h"
            #include "worldall.h"

            void worldAll() {
                helloWorld();
                bye("World");
            }
        """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8.12)
            project(world CXX)

            find_package(greetings)

            add_library(helloworld helloworld.cpp)
            target_link_libraries(helloworld greetings::hello)

            add_library(worldall worldall.cpp)
            target_link_libraries(worldall helloworld greetings::bye)
        """)
        test_pacakge_conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class GreetingsTestConan(ConanFile):
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake_find_package"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def test(self):
                    os.chdir("bin")
                    self.run(".%sexample" % os.sep)
        """)
        test_package_example_cpp = textwrap.dedent("""
            #include <iostream>
            #include "worldall.h"

            int main() {
                worldAll();
            }
        """)
        test_pacakge_cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8.12)
            project(PackageTest CXX)

            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/bin)
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})

            find_package(world)

            add_executable(example example.cpp)
            target_link_libraries(example world::worldall)
        """)
        client.save({"conanfile.py": conanfile,
                     "src/CMakeLists.txt": cmakelists,
                     "src/helloworld.h": helloworld_h,
                     "src/helloworld.cpp": helloworld_cpp,
                     "src/worldall.h": worldall_h,
                     "src/worldall.cpp": worldall_cpp,
                     "test_package/conanfile.py": test_pacakge_conanfile,
                     "test_package/CMakeLists.txt": test_pacakge_cmakelists,
                     "test_package/example.cpp": test_package_example_cpp})
        client.run("create .")
        self.assertIn("Hello World!", client.out)
        self.assertIn("Bye World!", client.out)
        print(client.out)
