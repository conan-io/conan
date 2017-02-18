import unittest
from conans.test.tools import TestClient
from nose.plugins.attrib import attr
import os


conanfile = """
from conans import ConanFile, CMake
import platform, os, shutil

class {name}Conan(ConanFile):
    name = "{name}"
    version = "0.1"
    requires = "{requires}"
    settings = "os", "compiler", "arch"
    generators = "cmake"
    exports = '*'

    def build(self):
        cmake = CMake(self.settings)
        if cmake.is_multi_configuration:
            cmd = 'cmake "%s" %s' % (self.conanfile_directory, cmake.command_line)
            self.run(cmd)
            self.run("cmake --build . --config Debug")
            self.run("cmake --build . --config Release")
        else:
            for config in ("Debug", "Release"):
                self.output.info("Building %s" % config)
                self.run('cmake "%s" %s -DCMAKE_BUILD_TYPE=%s'
                         % (self.conanfile_directory, cmake.command_line, config))
                self.run("cmake --build .")
                shutil.rmtree("CMakeFiles")
                os.remove("CMakeCache.txt")


    def package(self):
        self.copy(pattern="*.h", dst="include", keep_path=False)
        self.copy(pattern="*.lib", dst="lib", keep_path=False)
        self.copy(pattern="*lib*.a", dst="lib", keep_path=False)

    def package_info(self):
        self.cpp_info.release.libs = ["hello{name}"]
        self.cpp_info.debug.libs = ["hello{name}_d"]
"""

testconanfile = """
from conans import ConanFile, CMake
import platform, os, shutil

class TestConan(ConanFile):
    requires = "{requires}"
    settings = "os", "compiler", "arch"
    generators = "cmake"

    def build(self):
        cmake = CMake(self.settings)
        if cmake.is_multi_configuration:
            cmd = 'cmake "%s" %s' % (self.conanfile_directory, cmake.command_line)
            self.run(cmd)
            self.run("cmake --build . --config Debug")
            self.run("cmake --build . --config Release")
        else:
            for config in ("Debug", "Release"):
                self.output.info("Building %s" % config)
                self.run('cmake "%s" %s -DCMAKE_BUILD_TYPE=%s'
                         % (self.conanfile_directory, cmake.command_line, config))
                self.run("cmake --build .")
                shutil.rmtree("CMakeFiles")
                os.remove("CMakeCache.txt")

    def test(self):
        os.chdir("bin")
        self.run(".%sexample" % os.sep)
        self.run(".%sexample_d" % os.sep)

"""

hello_h = """
#pragma once

void hello{name}();
"""
hello_cpp = r"""#include "hello{name}.h"

#include <iostream>
using namespace std;

{includes}

void hello{name}(){{
#if  NDEBUG
    cout<<"Hello Release {name}\n";
#else
    cout<<"Hello Debug {name}\n";
#endif
    {other_calls}
}}
"""
main = """
#include "hello{name}.h"

int main(){{
    hello{name}();
}}
"""
cmake = """
project(MyHello)
cmake_minimum_required(VERSION 2.8.12)

include(${{CMAKE_BINARY_DIR}}/conanbuildinfo.cmake)
conan_basic_setup()

add_library(hello{name} hello.cpp)
set_target_properties(hello{name} PROPERTIES DEBUG_POSTFIX _d)
conan_target_link_libraries(hello{name})
add_executable(say_hello main.cpp)
set_target_properties(say_hello PROPERTIES DEBUG_POSTFIX _d)
target_link_libraries(say_hello hello{name})

"""
testcmake = """
project(MyHello)
cmake_minimum_required(VERSION 2.8.12)

include(${{CMAKE_BINARY_DIR}}/conanbuildinfo.cmake)
conan_basic_setup()

add_executable(example main.cpp)
set_target_properties(example PROPERTIES DEBUG_POSTFIX _d)
conan_target_link_libraries(example)

"""


@attr("slow")
class CMakeConfigsTest(unittest.TestCase):

    def test_package_configs_test(self):
        client = TestClient()
        name = "Hello0"
        requires = ""
        includes = ""
        other_calls = ""
        test_requires = "Hello0/0.1@memsharded/testing"
        client.save({"conanfile.py": conanfile.format(name=name, requires=requires),
                     "CMakeLists.txt": cmake.format(name=name),
                     "main.cpp": main.format(name=name),
                     "test_package/conanfile.py": testconanfile.format(name=name,
                                                                       requires=test_requires),
                     "test_package/CMakeLists.txt": testcmake.format(name=name),
                     "test_package/main.cpp": main.format(name=name),
                     "hello.cpp": hello_cpp.format(name=name, includes=includes,
                                                   other_calls=other_calls),
                     "hello%s.h" % name: hello_h.format(name=name)})

        client.run("test_package")
        self.assertIn("Hello Release Hello0", client.user_io.out)
        self.assertIn("Hello Debug Hello0", client.user_io.out)

    def cmake_multi_test(self):
        client = TestClient()

        requires = ""
        includes = ""
        other_calls = ""
        for name in ["Hello0", "Hello1", "Hello2"]:
            client.save({"conanfile.py": conanfile.format(name=name, requires=requires),
                         "CMakeLists.txt": cmake.format(name=name),
                         "main.cpp": main.format(name=name),
                         "hello.cpp": hello_cpp.format(name=name, includes=includes,
                                                       other_calls=other_calls),
                         "hello%s.h" % name: hello_h.format(name=name)},
                        clean_first=True)
            requires = "%s/0.1@memsharded/testing" % name
            includes = '#include "hello%s.h"' % name
            other_calls = "hello%s();" % name
            if name != "Hello2":
                client.run("export memsharded/testing")

        client.run('install . --build missing')
        client.run("build")
        cmd = os.sep.join([".", "bin", "say_hello"])
        client.runner(cmd, cwd=client.current_folder)
        self.assertIn("Hello Release Hello2 Hello Release Hello1 Hello Release Hello0",
                      " ".join(str(client.user_io.out).splitlines()))
        client.runner(cmd + "_d", cwd=client.current_folder)
        self.assertIn("Hello Debug Hello2 Hello Debug Hello1 Hello Debug Hello0",
                      " ".join(str(client.user_io.out).splitlines()))
