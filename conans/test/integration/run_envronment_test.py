import unittest

from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient, TestServer
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
import platform
from conans.build_info import command
import subprocess
from conans import tools


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
        servers = {"default": TestServer()}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
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
        client.run("create . Pkg/0.1@lasote/testing")
        client.run("upload Pkg* --all --confirm")
        client.run('remove "*" -f')
        client.run("search")
        self.assertIn("There are no packages", client.out)

        # MAKE SURE WE USE ANOTHER CLIENT, with another USER HOME PATH
        client2 = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        self.assertNotEqual(client2.base_folder, client.base_folder)
        reuse = '''from conans import ConanFile
class HelloConan(ConanFile):
    requires = "Pkg/0.1@lasote/testing"

    def build(self):
        self.run("say_hello", run_environment=True)
'''

        client2.save({"conanfile.py": reuse}, clean_first=True)
        client2.run("install .")
        client2.run("build .")
        self.assertIn("Hello Tool!", client2.out)

        if platform.system() != "Darwin":
            # This test is excluded from OSX, because of the SIP protection. CMake helper will
            # launch a subprocess with shell=True, which CLEANS the DYLD_LIBRARY_PATH. Injecting its
            # value via run_environment=True doesn't work, because it prepends its value to:
            # command = "cd [folder] && cmake [cmd]" => "DYLD_LIBRARY_PATH=[path] cd [folder] && cmake [cmd]"
            # and then only applies to the change directory "cd"
            # If CMake binary is in user folder, it is not under SIP, and it can work. For cmake installed in
            # system folders, then no possible form of "DYLD_LIBRARY_PATH=[folders] cmake" can work
            reuse = '''from conans import ConanFile, CMake, tools
class HelloConan(ConanFile):
    exports = "CMakeLists.txt"
    requires = "Pkg/0.1@lasote/testing"

    def build(self):
        with tools.run_environment(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()
    '''
            cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)
execute_process(COMMAND say_hello)
"""
            client2.save({"conanfile.py": reuse,
                          "CMakeLists.txt": cmake}, clean_first=True)
            client2.run("install . -g virtualrunenv")
            client2.run("build .")
            self.assertIn("Hello Tool!", client2.out)
        else:
            client2.run("install . -g virtualrunenv")

        with tools.chdir(client2.current_folder):
            if platform.system() == "Windows":
                command = "activate_run.bat && say_hello"
            else:
                # It is not necessary to use the DYLD_LIBRARY_PATH in OSX because the activate_run.sh
                # will work perfectly. It is inside the bash, so the loader will use DYLD_LIBRARY_PATH
                # values. It also works in command line with export DYLD_LIBRARY_PATH=[path] and then
                # running, or in the same line "$ DYLD_LIBRARY_PATH=[path] say_hello"
                command = "bash -c 'source activate_run.sh && say_hello'"

            output = subprocess.check_output(command, shell=True)
            self.assertIn("Hello Tool!", str(output))
