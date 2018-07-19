import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, TestServer
from conans.test.utils.cpp_test_files import cpp_hello_conan_files

class RunEnvironmentTest(unittest.TestCase):

    def test_run_environment(self):
        client = TestClient()
        files = cpp_hello_conan_files("Hello0", "0.1")
        files[CONANFILE] = files[CONANFILE].replace('self.copy(pattern="*.so", dst="lib", keep_path=False)',
                                                    '''self.copy(pattern="*.so", dst="lib", keep_path=False)
        self.copy(pattern="*say_hello*", dst="bin", keep_path=False)''')
        client.save(files)
        client.run("export . lasote/stable")

        reuse = '''
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
'''

        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("install . --build missing")
        client.run("build .")
        self.assertIn("Hello Hello0", client.out)

    def test_shared_run_environment(self):
        test_server = TestServer(users={"user": "mypass"})
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("user", "mypass")]})
        cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)

add_library(hello SHARED hello.cpp)
add_executable(say_hello main.cpp)
target_link_libraries(say_hello hello)"""
        hello_h = """#ifdef WIN32
  #define HELLO_EXPORT __declspec(dllexport)
#else
  #define HELLO_EXPORT
#endif

HELLO_EXPORT void hello();
"""
        hello_cpp = r"""#include "hello.h"
#include <iostream>
void hello(){
    std::cout<<"Hello Tool!\n";
}
"""
        main = """#include "hello.h"
        int main(){
            hello();
        }
        """
        conanfile = """from conans import ConanFile, CMake
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
"""
        client.save({"conanfile.py": conanfile,
                     "CMakeLists.txt": cmake,
                     "main.cpp": main,
                     "hello.cpp": hello_cpp,
                     "hello.h": hello_h})
        client.run("create . Pkg/0.1@user/testing")
        client.run("upload Pkg/0.1@user/testing -c --all")
        client.run('remove "*" -f')

        reuse = '''from conans import ConanFile
class HelloConan(ConanFile):
    requires = "Pkg/0.1@user/testing"

    def build(self):
        self.run("say_hello", run_environment=True)
'''
        client2 = TestClient(servers=servers, users={"default": [("user", "mypass")]})

        client2.save({"conanfile.py": reuse}, clean_first=True)
        client2.run("install .")
        client2.run("build .")
        self.assertIn("Hello Tool!", client2.out)
