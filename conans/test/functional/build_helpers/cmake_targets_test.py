import os
import platform
import unittest

from nose.plugins.attrib import attr

from conans.test.utils.tools import TestClient
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
    def transitive_flags_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Charlie(ConanFile):
    def package_info(self):
        self.cpp_info.sharedlinkflags = ["CharlieFlag"]
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Charlie/0.1@user/testing")
        conanfile = """from conans import ConanFile
class Beta(ConanFile):
    requires = "Charlie/0.1@user/testing"
    def package_info(self):
        self.cpp_info.sharedlinkflags = ["BetaFlag"]
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Beta/0.1@user/testing")
        conanfile = """from conans import ConanFile
class Alpha(ConanFile):
    requires = "Beta/0.1@user/testing"
"""
        client.save({"conanfile.py": conanfile})
        client.run("install . -g cmake")
        cmake = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn('set(CONAN_SHARED_LINKER_FLAGS '
                      '"CharlieFlag BetaFlag ${CONAN_SHARED_LINKER_FLAGS}")', cmake)

    def header_only_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py,
                     "hello.h": hello})
        client.run("export . lasote/testing")
        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake,
                     "main.cpp": main}, clean_first=True)

        client.run('install . -g cmake')
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

            client.run('install . %s -s build_type=Debug -g cmake_multi' % debug_install)
            client.run('install . %s -s build_type=Release -g cmake_multi' % release_install)
            client.runner("cmake .", cwd=client.current_folder)
            self.assertNotIn("WARN: Unknown compiler '", client.user_io.out)
            self.assertNotIn("', skipping the version check...", client.user_io.out)
            self.assertIn("Configuring done", client.user_io.out)
            self.assertIn("Generating done", client.user_io.out)
            self.assertIn("Build files have been written", client.user_io.out)

    @unittest.skipUnless(platform.system() == "Darwin", "Requires Macos")
    def apple_framework_test(self):

        client = TestClient()
        conanfile_fr = conanfile_py + '''
    def package_info(self):
        self.cpp_info.sharedlinkflags = ["-framework Foundation"]
        self.cpp_info.exelinkflags = self.cpp_info.sharedlinkflags
'''
        client.save({"conanfile.py": conanfile_fr,
                     "hello.h": hello})

        client.run("export . lasote/testing")
        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake,
                     "main.cpp": main}, clean_first=True)

        client.run("install . -g cmake")
        bili = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("-framework Foundation", bili)

    @unittest.skipUnless(platform.system() == "Darwin", "Requires Macos")
    def custom_apple_framework_test(self):
        """Build a custom apple framework and reuse it"""
        client = TestClient()
        lib_c = r"""
#include <stdio.h>
#include "MyFramework.h"

void hello(){
    printf("HELLO FRAMEWORK!");
}
"""

        lib_h = r"""
void hello();
"""
        conanfile = '''
import os
from shutil import copyfile
from conans import ConanFile, CMake

class MyFrameworkConan(ConanFile):

    options = {"shared": [True, False]}
    default_options = "shared=True"
    exports = "*"
    generators = "cmake"
    
    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
    
    def package(self):
        self.copy(pattern="*", src="lib", keep_path=True)
    
    def package_info(self):
        flag_f_location = '-F "%s"' % self.package_folder
        self.cpp_info.cflags.append(flag_f_location)
        self.cpp_info.sharedlinkflags.extend([flag_f_location, "-framework MyFramework"])
        self.cpp_info.exelinkflags = self.cpp_info.sharedlinkflags
'''

        cmake = """
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello C)
cmake_minimum_required(VERSION 2.8.12)
include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup(KEEP_RPATHS)
add_library(MyFramework MyFramework.c MyFramework.h)

set_target_properties(MyFramework PROPERTIES
  FRAMEWORK TRUE
  FRAMEWORK_VERSION C
  MACOSX_FRAMEWORK_IDENTIFIER MyFramework
  PUBLIC_HEADER MyFramework.h
)

 """

        files = {"MyFramework.c": lib_c, "conanfile.py": conanfile, "MyFramework.h": lib_h,
                 "CMakeLists.txt": cmake}
        client.save(files, clean_first=True)
        client.run("create . MyFramework/1.0@user/testing")

        reuse = """from conans import ConanFile, CMake

class HelloConan(ConanFile):
    requires = "MyFramework/1.0@user/testing"
    generators = "cmake"
    exports = "*"
    
    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

"""

        cmake = """
set(CMAKE_VERBOSE_MAKEFILE ON)
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello C)
cmake_minimum_required(VERSION 2.8.12)
include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup(KEEP_RPATHS)
add_executable(say_hello main.c)    
"""

        main = """
#include "MyFramework/MyFramework.h"
int main(){
    hello();
}     
"""
        files = {"main.c": main, "conanfile.py": reuse,
                 "CMakeLists.txt": cmake}
        client.save(files, clean_first=True)
        client.run("install . ")
        client.run("build . ")
        client.runner("bin/say_hello", cwd=client.current_folder)
        self.assertIn("HELLO FRAMEWORK!", client.out)
