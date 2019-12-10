import os
import platform
import textwrap
import unittest

from parameterized import parameterized

from conans.util.files import mkdir
from conans.test.utils.tools import TestClient


class DevLayoutTest(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake, CMakeLayout

        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            options = {"shared": [True, False]}
            default_options = {"shared": False}
            generators = "cmake"
            exports_sources = "src/*"
            generators = "cmake"
            # IDEA TO HAVE THIS SIMPLIFIED DECLARATION: layout = "cmake"

            def layout(self):
                mylayout = CMakeLayout(self)
                # Default, will be overriden by local "build-folder" arg
                mylayout.build = "build"
                return mylayout

            def build(self):
                cmake = CMake(self) # Opt-in is defined having toolchain
                cmake.configure()
                cmake.build()

            def package(self):
                # WITH THE SIMPLIFIED DECLARATION, THIS WILL NOT BE POSSIBLE
                self.layout().package()

            def package_info(self):
                self.cpp_info.libs = ["hello"]
            """)
    cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 2.8.12)
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)    
        project(HelloWorldLib CXX)

        add_library(hello hello.cpp)
        add_executable(app app.cpp)
        target_link_libraries(app PRIVATE hello)
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
        cmake_minimum_required(VERSION 2.8.12)
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
            
            def imports(self):
                self.copy(pattern="*.dll", dst="bin", src="#bindir")

            def test(self):
                os.chdir("bin")
                self.run(".%sapp" % os.sep)
        """)

    def setUp(self):
        client = TestClient()
        client.save({"conanfile.py": self.conanfile,
                     "src/CMakeLists.txt": self.cmake,
                     "src/hello.cpp": self.hellopp,
                     "src/hello.h": self.helloh,
                     "src/app.cpp": self.app,
                     "test_package/app.cpp": self.app,
                     "test_package/CMakeLists.txt": self.test_cmake,
                     "test_package/conanfile.py": self.test_conanfile
                     })
        self.client = client

    def cache_create_test(self):
        # Cache creation
        client = self.client
        client.run("create . pkg/0.1@user/testing")
        self.assertIn("pkg/0.1@user/testing package(): Packaged 1 '.h' file: hello.h", client.out)
        self.assertIn("Hello World Release!", client.out)

    def cache_create_shared_test(self):
        # Cache creation
        client = self.client
        client.run("create . pkg/0.1@user/testing -o pkg:shared=True")
        self.assertIn("pkg/0.1@user/testing package(): Packaged 1 '.dll' file: hello.dll",
                      client.out)
        self.assertIn("pkg/0.1@user/testing package(): Packaged 1 '.h' file: hello.h", client.out)
        self.assertIn("imports(): Copied 1 '.dll' file: hello.dll", client.out)
        self.assertIn("Hello World Release!", client.out)

    @unittest.skipIf(platform.system() != "Windows", "Needs windows")
    @parameterized.expand([(True,), (False,)])
    def local_build_test(self, shared):
        client = self.client
        mkdir(os.path.join(client.current_folder, "build"))
        client.run("install .")
        shared = "-DBUILD_SHARED_LIBS=ON" if shared else ""
        with client.chdir("build"):
            client.run_command('cmake ../src -G "Visual Studio 15 Win64" %s' % shared)
            client.run_command("cmake --build . --config Release")
            client.run_command(r"Release\\app.exe")
            self.assertIn("Hello World Release!", client.out)
            client.run_command("cmake --build . --config Debug")
            client.run_command(r"Debug\\app.exe")
            self.assertIn("Hello World Debug!", client.out)

        client.run("editable add . pkg/0.1@user/testing")
        # Consumer of editable package
        client2 = TestClient(cache_folder=client.cache_folder)
        consumer = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake, tools, CMakeLayout

            class Consumer(ConanFile):
                settings = "os", "compiler", "build_type", "arch"
                requires = "pkg/0.1@user/testing"
                generators = "cmake_find_package_multi"
                
                def layout(self):
                    mylayout = CMakeLayout(self)
                    mylayout.build = "build"
                    return mylayout
                    
                def imports(self):
                    lay = self.layout()
                    self.copy(pattern="*.dll", dst=lay.build_bindir, src="#bindir")
            """)

        test_cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.8.12)
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            project(Greet CXX)
            set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR} ${CMAKE_MODULE_PATH})
            set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR} ${CMAKE_PREFIX_PATH})
            find_package(pkg)
            
            add_executable(app app.cpp)
            target_link_libraries(app pkg::pkg)
            """)
        client2.save({"app.cpp": self.app,
                      "CMakeLists.txt": test_cmake,
                      "conanfile.py": consumer})
        client2.run("install .")
        print client2.out
        client2.run("install . -s build_type=Debug")
        with client2.chdir("build"):
            client2.run_command('cmake .. -G "Visual Studio 15 Win64"')
            print client2.out
            client2.run_command("cmake --build . --config Release")
            # alternative 1: imports() copy DLLs. Does not work for continuous dev
            #                ok for cached dependencies, different Debug/Release output
            # alternative 2: virtualrunenv switch debug/release???
            # alternative 3: environment in cmake => path in MSBuild
            client2.run_command(r"Release\\app.exe")
            self.assertIn("Hello World Release!", client2.out)
            client2.run_command("cmake --build . --config Debug")
            client2.run_command(r"Debug\\app.exe")
            self.assertIn("Hello World Debug!", client2.out)

        # do changes
        client.save({"src/hello.cpp": self.hellopp.replace("World", "Moon")})
        with client.chdir("build"):
            client.run_command("cmake --build . --config Release")
            client.run_command(r"Release\\app.exe")
            self.assertIn("Hello Moon Release!", client.out)
            client.run_command("cmake --build . --config Debug")
            client.run_command(r"Debug\\app.exe")
            self.assertIn("Hello Moon Debug!", client.out)

        # It is necessary to "install" again, to fire the imports() and copy the DLLs
        client2.run("install .")
        client2.run("install . -s build_type=Debug")
        with client2.chdir("build"):
            client2.run_command("cmake --build . --config Release")
            client2.run_command(r"Release\\app.exe")
            self.assertIn("Hello Moon Release!", client2.out)
            client2.run_command("cmake --build . --config Debug")
            client2.run_command(r"Debug\\app.exe")
            self.assertIn("Hello Moon Debug!", client2.out)
