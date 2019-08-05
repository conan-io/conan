import os
import textwrap
import unittest

from conans.util.files import mkdir
from conans.test.utils.tools import TestClient


class ToolChainTest(unittest.TestCase):

    def basic_test(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake, CMakeToolchain

            class Pkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                generators = "cmake"
                exports_sources = "*"
                generators = "cmake"
            
                def toolchain(self):
                    return CMakeToolchain(self)    
            
                def build(self):
                    cmake = CMake(self) # Opt-in is defined having toolchain
                    cmake.configure()
                    cmake.build()
            
                def package(self):
                    self.toolchain().package()
            
                def package_info(self):
                    self.cpp_info.libs = ["hello"]
                """)
        cmake = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)    
            project(HelloWorldLib CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup(NO_OUTPUT_DIRS)

            add_library(hello hello.cpp)
            """)
        hellopp = textwrap.dedent("""
            #include "hello.h"

            std::string hello(){
                #ifdef 	_M_IX86
                    #ifdef NDEBUG
                    return  "Hello World Release 32bits!";
                    #else
                    return  "Hello World Debug 32bits!";
                    #endif
                #else
                    #ifdef NDEBUG
                    return  "Hello World Release!";
                    #else
                    return  "Hello World Debug!";
                    #endif
                #endif
            }
            """)
        helloh = textwrap.dedent("""
            #pragma once
            #include <string>
            
            #ifdef WIN32
              #define HELLO_EXPORT __declspec(dllexport)
            #else
              #define HELLO_EXPORT
            #endif
            
            HELLO_EXPORT 
            std::string hello();
            """)
        app = textwrap.dedent(r"""
            #include <iostream>
            #include "hello.h"
            
            int main(){
                std::cout << "****\n" << hello() << "\n****\n\n";
            }
            """)
        test_cmake = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            
            project(Greet CXX)
            
            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()
            
            add_executable(app app.cpp)
            target_link_libraries(app ${CONAN_LIBS})
            """)
        test_conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake, tools
            
            class Test(ConanFile):
                settings = "os", "compiler", "build_type", "arch"
                generators = "cmake"
            
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
            
                def test(self):
                    os.chdir("bin")
                    self.run(".%sapp" % os.sep)
            """)
        client.save({"conanfile.py": conanfile,
                     "src/CMakeLists.txt": cmake,
                     "src/hello.cpp": hellopp,
                     "src/hello.h": helloh,
                     "test_package/app.cpp": app,
                     "test_package/CMakeLists.txt": test_cmake,
                     "test_package/conanfile.py": test_conanfile
                     })

        # Cache creation
        client.run("create . pkg/0.1@user/testing")
        print client.out
        self.assertIn("pkg/0.1@user/testing package(): Packaged 1 '.h' file: hello.h", client.out)
        self.assertIn("Hello World Release!", client.out)

        # Local flow
        mkdir(os.path.join(client.current_folder, "build"))
        with client.chdir("build"):
            client.run("install ..")
            client.run("build ..")
            print client.out
            client.run("package .. -pf=pkg")
            print client.out
            self.assertIn("conanfile.py: Package 'pkg' created", client.out)

