import unittest
from conans.test.utils.tools import TestClient
from nose.plugins.attrib import attr
import platform
import os
from conans.test.utils.multi_config import multi_config_files
from conans.client.cmake import clean_sh_from_path

conanfile_py = """
from conans import ConanFile, CMake
import platform, os, shutil

class {name}Conan(ConanFile):
    name = "{name}"
    version = "0.1"
    requires = {requires}
    settings = "os", "compiler", "arch", "build_type"
    generators = "cmake"
    exports = '*'

    def build(self):
        with open("hello{name}.h", "a") as f:
            f.write('#define HELLO{name}BUILD "%s"' % self.settings.build_type)
        cmake = CMake(self)
        self.run('cmake %s' % (cmake.command_line))
        self.run("cmake --build . %s" % cmake.build_config)

    def package(self):
        self.copy(pattern="*.h", dst="include", keep_path=False)
        self.copy(pattern="*.lib", dst="lib", keep_path=False)
        self.copy(pattern="*lib*.a", dst="lib", keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["hello{name}"]
        self.cpp_info.defines = ['HELLO{name}DEFINE="%s"' % self.settings.build_type]
"""


hello_h = """
#pragma once
{includes}
void hello{name}();
"""
hello_cpp = r"""#include "hello{name}.h"

#include <iostream>
using namespace std;

void hello{name}(){{
#if  NDEBUG
    cout<<"Hello Release {name}\n";
#else
    cout<<"Hello Debug {name}\n";
#endif
    {other_calls}
}}
"""

cmake_pkg = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)

include(${{CMAKE_BINARY_DIR}}/conanbuildinfo.cmake)
conan_basic_setup()

add_library(hello{name} hello.cpp)
conan_target_link_libraries(hello{name})
"""


def package_files(name, deps=None):
    requires = ', '.join('"%s/0.1@lasote/testing"' % r for r in deps or []) or '""'
    includes = "\n".join(['#include "hello%s.h"' % d for d in deps or []])
    other_calls = "\n".join(["hello%s();" % d for d in deps or []])
    return {"conanfile.py": conanfile_py.format(name=name, requires=requires),
            "hello%s.h" % name: hello_h.format(name=name, includes=includes),
            "hello.cpp": hello_cpp.format(name=name, other_calls=other_calls),
            "CMakeLists.txt": cmake_pkg.format(name=name)}


conanfile = """[requires]
Hello1/0.1@lasote/testing
[generators]
cmake_multi
"""

cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)

# Some cross-building toolchains will define this
set(CMAKE_FIND_ROOT_PATH "/some/path")
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
include(${CMAKE_BINARY_DIR}/conanbuildinfo_multi.cmake)
conan_basic_setup()

add_executable(say_hello main.cpp)
conan_target_link_libraries(say_hello)
"""

cmake_targets = cmake.replace("conan_basic_setup()", "conan_basic_setup(TARGETS)")

main = """
#include "helloHello1.h"
#include <iostream>

int main(){{
    std::cout<<"Hello0:"<<HELLOHello0BUILD<<" Hello1:"<<HELLOHello1BUILD<<std::endl;
    std::cout<<"Hello0Def:"<<HELLOHello0DEFINE<<" Hello1Def:"<<HELLOHello1DEFINE<<std::endl;
    helloHello1();
    return 0;
}}
"""

main2 = """
#include "helloHello1.h"
#include <iostream>

int main(){{
    std::cout<<" Hello1:"<<HELLOHello1BUILD<<std::endl;
    std::cout<<" Hello1Def:"<<HELLOHello1DEFINE<<std::endl;
    helloHello1();
    return 0;
}}
"""


@attr("slow")
class CMakeMultiTest(unittest.TestCase):

    def cmake_multi_find_test(self):
        if platform.system() not in ["Windows", "Linux"]:
            return
        client = TestClient()
        conanfile = """from conans import ConanFile, CMake
class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    settings = "build_type"
    exports = '*'

    def package(self):
        self.copy(pattern="*", src="%s" % self.settings.build_type)
        """

        client.save({"conanfile.py": conanfile,
                     "Debug/FindHello.cmake": 'message(STATUS "FIND HELLO DEBUG!")',
                     "Release/FindHello.cmake": 'message(STATUS "FIND HELLO RELEASE!")'})
        client.run("export lasote/testing")
        cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8)
include(conanbuildinfo_multi.cmake)
conan_basic_setup()
find_package(Hello)
"""
        conanfile = """from conans import ConanFile, CMake
class HelloConan(ConanFile):
    requires = "Hello/0.1@lasote/testing"
    settings = "build_type"
    generators = "cmake_multi"
    """
        client.save({"conanfile.py": conanfile,
                     "CMakeLists.txt": cmake}, clean_first=True)

        client.run("install . --build=missing ")
        client.run("install . -s build_type=Debug --build=missing ")

        with clean_sh_from_path():
            generator = "MinGW Makefiles" if platform.system() == "Windows" else "Unix Makefiles"
            client.runner('cmake . -G "%s" -DCMAKE_BUILD_TYPE=Debug' % generator,
                          cwd=client.current_folder)
            self.assertIn("FIND HELLO DEBUG!", client.user_io.out)
            self.assertNotIn("FIND HELLO RELEASE!", client.user_io.out)

            client.init_dynamic_vars()  # to reset output
            client.runner('cmake . -G "%s" -DCMAKE_BUILD_TYPE=Release' % generator,
                          cwd=client.current_folder)
            self.assertIn("FIND HELLO RELEASE!", client.user_io.out)
            self.assertNotIn("FIND HELLO DEBUG!", client.user_io.out)

    def cmake_multi_test(self):
        if platform.system() not in ["Windows", "Darwin"]:
            return
        client = TestClient()

        client.save(multi_config_files("Hello0", test=False), clean_first=True)
        client.run("export lasote/testing")
        client.run("install Hello0/0.1@lasote/testing --build=missing")
        client.save(package_files("Hello1", ["Hello0"]), clean_first=True)
        client.run("export lasote/testing")

        if platform.system() == "Windows":
            generator = "Visual Studio 14 Win64"
            debug_install = '-s compiler="Visual Studio" -s compiler.version=14 -s compiler.runtime=MDd'
            release_install = '-s compiler="Visual Studio" -s compiler.version=14 -s compiler.runtime=MD'
        elif platform.system() == "Darwin":
            generator = "Xcode"
            debug_install = ''
            release_install = ''

        # better in one test instead of two, because install time is amortized
        for cmake_file in (cmake, cmake_targets, ):
            client.save({"conanfile.txt": conanfile,
                         "CMakeLists.txt": cmake_file,
                         "main.cpp": main}, clean_first=True)
            client.run('install -s build_type=Debug %s --build=missing' % debug_install)
            client.run('install -s build_type=Release %s --build=missing' % release_install)

            client.runner('cmake . -G "%s"' % generator, cwd=client.current_folder)
            self.assertNotIn("WARN: Unknown compiler '", client.user_io.out)
            self.assertNotIn("', skipping the version check...", client.user_io.out)
            client.runner('cmake --build . --config Debug', cwd=client.current_folder)
            hello_comand = os.sep.join([".", "Debug", "say_hello"])
            client.runner(hello_comand, cwd=client.current_folder)

            self.assertIn("Hello0:Debug Hello1:Debug", client.user_io.out)
            self.assertIn("Hello0Def:Debug Hello1Def:Debug", client.user_io.out)
            self.assertIn("Hello Debug Hello1", client.user_io.out)
            self.assertIn("Hello Debug Hello0", client.user_io.out)
            client.runner('cmake --build . --config Release', cwd=client.current_folder)
            hello_comand = os.sep.join([".", "Release", "say_hello"])
            client.runner(hello_comand, cwd=client.current_folder)

            self.assertIn("Hello0:Release Hello1:Release", client.user_io.out)
            self.assertIn("Hello0Def:Release Hello1Def:Release", client.user_io.out)
            self.assertIn("Hello Release Hello1", client.user_io.out)
            self.assertIn("Hello Release Hello0", client.user_io.out)
            if cmake_file == cmake_targets:
                self.assertIn("Conan: Using cmake targets configuration", client.user_io.out)
            else:
                self.assertIn("Conan: Using cmake global configuration", client.user_io.out)
