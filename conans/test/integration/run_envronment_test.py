import os
import platform
import subprocess
import unittest

from conans.client import tools
from conans.paths import CONANFILE
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient, TestServer


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
        """Verify that Conan sets RunEnvironment so that system can find shared libraries.

        A producer package contains a shared library and an execurable linked against it.

        This test verifies RunEnvironment is used in different contexts of consumer package:
        - ConanFile.run(run_environment=True) method
        - tools.run_environment() helper (except for MacOS)
        - virtualrunenv generator

        To reduce risk of false positive results:
        - package with shared library is deployed into different user folder via TestServer
        - The consumer tries to execute the imported shared library and executable in the same
          directory, and it fails in Linux, but works on OSX and WIndows.
        - Then I move the shared library to a different directory, and it fails,
          I'm making sure that there is no harcoded rpaths messing.
        - Finally I use the virtualrunenvironment that declares de LD_LIBRARY_PATH,
          PATH and DYLD_LIBRARY_PATH to run the executable, and.. magic!
          it's running agains the shared in the local cache.
        """
        servers = {"default": TestServer()}
        client1 = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
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
        client1.save({"conanfile.py": conanfile,
                     "CMakeLists.txt": cmake,
                     "main.cpp": main,
                     "hello.cpp": hello_cpp,
                     "hello.h": hello_h})
        client1.run("create . Pkg/0.1@lasote/testing")
        client1.run("upload Pkg* --all --confirm")
        client1.run('remove "*" -f')
        client1.run("search")
        self.assertIn("There are no packages", client1.out)

        # MAKE SURE WE USE ANOTHER CLIENT, with another USER HOME PATH
        client2 = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        self.assertNotEqual(client2.base_folder, client1.base_folder)
        consumer_self_run = '''from conans import ConanFile
class HelloConan(ConanFile):
    requires = "Pkg/0.1@lasote/testing"

    def build(self):
        self.run("say_hello", run_environment=True)
'''

        client2.save({"conanfile.py": consumer_self_run}, clean_first=True)
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
            consumer_tools_run_environment = '''from conans import ConanFile, CMake, tools
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
            client2.save({"conanfile.py": consumer_tools_run_environment,
                          "CMakeLists.txt": cmake}, clean_first=True)
            client2.run("install .")
            client2.run("build .")
            self.assertIn("Hello Tool!", client2.out)

        consumer_virtual_runenv = '''[requires]
Pkg/0.1@lasote/testing
[generators]
virtualrunenv
[imports]
bin, * -> ./bin
lib, * -> ./bin
'''
        client2.save({"conanfile.txt": consumer_virtual_runenv},
                     clean_first=True)
        client2.run("install .")

        # Break possible rpaths built in the exe with absolute paths
        os.rename(
            os.path.join(client2.current_folder, "bin"),
            os.path.join(client2.current_folder, "bin2"))

        with tools.chdir(os.path.join(client2.current_folder, "bin2")):
            if platform.system() == "Windows":
                self.assertEqual(os.system("say_hello.exe"), 0)
            elif platform.system() == "Darwin":
                self.assertEqual(os.system("./say_hello"), 0)
            else:
                self.assertNotEqual(os.system("./say_hello"), 0)
                self.assertEqual(
                    os.system("LD_LIBRARY_PATH=$(pwd) ./say_hello"), 0)
                self.assertEqual(os.system("LD_LIBRARY_PATH=. ./say_hello"), 0)

            # If we move the shared library it won't work, at least we use the virtualrunenv
            os.mkdir(os.path.join(client2.current_folder, "bin2", "subdir"))
            name = {
                "Darwin": "libhello.dylib",
                "Windows": "hello.dll"
            }.get(platform.system(), "libhello.so")

            os.rename(
                os.path.join(client2.current_folder, "bin2", name),
                os.path.join(client2.current_folder, "bin2", "subdir", name))

            if platform.system() == "Windows":
                self.assertNotEqual(os.system("say_hello.exe"), 0)
            elif platform.system() == "Darwin":
                self.assertNotEqual(os.system("./say_hello"), 0)
            else:
                self.assertNotEqual(
                    os.system("LD_LIBRARY_PATH=$(pwd) ./say_hello"), 0)

            # Will use the shared library from the local cache
            if platform.system() != "Windows":
                # It is not necessary to use the DYLD_LIBRARY_PATH in OSX because the activate_run.sh
                # will work perfectly. It is inside the bash, so the loader will use DYLD_LIBRARY_PATH
                # values. It also works in command line with export DYLD_LIBRARY_PATH=[path] and then
                # running, or in the same line "$ DYLD_LIBRARY_PATH=[path] say_hello"
                command = "bash -c 'source ../activate_run.sh && ./say_hello'"
            else:
                command = "cd .. && activate_run.bat && cd bin2 && say_hello.exe"

            output = subprocess.check_output(command, shell=True)
            self.assertIn("Hello Tool!", str(output))
