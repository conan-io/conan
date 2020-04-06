# coding=utf-8

import platform
import textwrap
import unittest

from conans.client import tools
from conans.paths import CONANFILE
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient, TestServer
from conans.util.runners import check_output_runner


class RunEnvironmentTest(unittest.TestCase):

    def test_run_environment(self):
        client = TestClient()
        files = cpp_hello_conan_files("Hello0", "0.1")
        files[CONANFILE] = files[CONANFILE].replace(
            'self.copy(pattern="*.so", dst="lib", keep_path=False)',
            '''self.copy(pattern="*.so", dst="lib", keep_path=False)
        self.copy(pattern="*say_hello*", dst="bin", keep_path=False)''')
        client.save(files)
        client.run("export . lasote/stable")

        reuse = textwrap.dedent("""
            from conans import ConanFile, RunEnvironment, tools

            class HelloConan(ConanFile):
                name = "Reuse"
                version = "0.1"
                build_policy = "missing"
                requires = "Hello0/0.1@lasote/stable"
            
                def build(self):
                    run_env = RunEnvironment(self)
                    with tools.environment_append(run_env.vars):
                        self.run("say_hello")
        """)

        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("install . --build missing")
        client.run("build .")
        self.assertIn("Hello Hello0", client.out)


class RunEnvironmentSharedTest(unittest.TestCase):

    def setUp(self):
        self.servers = {"default": TestServer()}
        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        cmake = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            project(MyHello CXX)
            cmake_minimum_required(VERSION 2.8.12)
            add_library(hello SHARED hello.cpp)
            add_executable(say_hello main.cpp)
            target_link_libraries(say_hello hello)
        """)

        hello_h = textwrap.dedent("""
            #ifdef WIN32
              #define HELLO_EXPORT __declspec(dllexport)
            #else
              #define HELLO_EXPORT
            #endif
            
            HELLO_EXPORT void hello();
        """)

        hello_cpp = textwrap.dedent("""
            #include "hello.h"
            #include <iostream>
            void hello(){
                std::cout << "Hello Tool!\\n";
            }
        """)

        main = textwrap.dedent("""
            #include "hello.h"
            int main(){
                hello();
            }
        """)

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake
            class Pkg(ConanFile):
                exports_sources = "*"
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
            
                def package(self):
                    self.copy("*say_hello.exe", dst="bin", keep_path=False)
                    self.copy("*say_hello", dst="bin", keep_path=False)
                    self.copy(pattern="*.dll", dst="bin", keep_path=False)
                    self.copy(pattern="*.dylib", dst="lib", keep_path=False)
                    self.copy(pattern="*.so", dst="lib", keep_path=False)
        """)

        client.save({"conanfile.py": conanfile,
                     "CMakeLists.txt": cmake,
                     "main.cpp": main,
                     "hello.cpp": hello_cpp,
                     "hello.h": hello_h})
        client.run("create . Pkg/0.1@lasote/testing")
        client.run("upload Pkg* --all --confirm")
        client.run('remove "*" -f')
        client.run("search")
        self.assertIn("There are no packages", client.out)

    def test_run_with_run_environment(self):
        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

        reuse = textwrap.dedent("""
            from conans import ConanFile
            class HelloConan(ConanFile):
                requires = "Pkg/0.1@lasote/testing"

                def build(self):
                    self.run("say_hello", run_environment=True)
        """)

        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("install .")
        client.run("build .")
        self.assertIn("Hello Tool!", client.out)

    @unittest.skipIf(platform.system() == "Darwin", "SIP protection (read comment)")
    def test_with_tools_run_environment(self):
        # This test is excluded from OSX, because of the SIP protection. CMake helper will
        # launch a subprocess with shell=True, which CLEANS the DYLD_LIBRARY_PATH. Injecting its
        # value via run_environment=True doesn't work, because it prepends its value to:
        # command = "cd [folder] && cmake [cmd]" =>
        #                 "DYLD_LIBRARY_PATH=[path] cd [folder] && cmake [cmd]"
        # and then only applies to the change directory "cd"
        # If CMake binary is in user folder, it is not under SIP, and it can work. For cmake
        # installed in system folders, then no possible form of "DYLD_LIBRARY_PATH=[folders] cmake"
        # can work
        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

        reuse = textwrap.dedent("""
            from conans import ConanFile, CMake, tools
            class HelloConan(ConanFile):
                exports = "CMakeLists.txt"
                requires = "Pkg/0.1@lasote/testing"

                def build(self):
                    with tools.run_environment(self):
                        cmake = CMake(self)
                        cmake.configure()
                        cmake.build()
        """)

        cmake = textwrap.dedent("""
            set(CMAKE_CXX_COMPILER_WORKS 1)
            set(CMAKE_CXX_ABI_COMPILED 1)
            project(MyHello CXX)
            cmake_minimum_required(VERSION 2.8.12)
            execute_process(COMMAND say_hello)
        """)

        client.save({"conanfile.py": reuse,
                     "CMakeLists.txt": cmake}, clean_first=True)
        client.run("install .")
        client.run("build .")
        self.assertIn("Hello Tool!", client.out)

    def test_virtualrunenv(self):
        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        client.run("install Pkg/0.1@lasote/testing -g virtualrunenv")

        with tools.chdir(client.current_folder):
            if platform.system() == "Windows":
                command = "activate_run.bat && say_hello"
            else:
                # It is not necessary to use the DYLD_LIBRARY_PATH in OSX because the activate_run.sh
                # will work perfectly. It is inside bash, so the loader will use DYLD_LIBRARY_PATH
                # values. It also works in command line with export DYLD_LIBRARY_PATH=[path] and then
                # running, or in the same line "$ DYLD_LIBRARY_PATH=[path] say_hello"
                command = "bash -c 'source activate_run.sh && say_hello'"

            output = check_output_runner(command)
            self.assertIn("Hello Tool!", output)
