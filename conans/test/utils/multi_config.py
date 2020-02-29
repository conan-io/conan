conanfile = """
from conans import ConanFile, CMake
import platform, os, shutil

class {name}Conan(ConanFile):
    name = "{name}"
    version = "0.1"
    requires = {requires}
    settings = "os", "compiler", "arch"
    generators = "cmake"
    exports = '*'

    def build(self):
        cmake = CMake(self)
        if cmake.is_multi_configuration:
            cmd = 'cmake "%s" %s' % (self.source_folder, cmake.command_line)
            self.run(cmd)
            self.run("cmake --build . --config Debug")
            self.run("cmake --build . --config Release")
            self.run("cmake --build . --config RelWithDebInfo")
            self.run("cmake --build . --config MinSizeRel")
        else:
            for config in ("Debug", "Release", "RelWithDebInfo", "MinSizeRel"):
                self.output.info("Building %s" % config)
                self.run('cmake "%s" %s -DCMAKE_BUILD_TYPE=%s'
                         % (self.source_folder, cmake.command_line, config))
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
        self.cpp_info.relwithdebinfo.libs = ["hello{name}_relwithdebinfo"]
        self.cpp_info.minsizerel.libs = ["hello{name}_minsizerel"]

        self.cpp_info.release.defines = ['HELLO{name}DEFINE="Release"',
                                         'HELLO{name}BUILD="Release"']
        self.cpp_info.debug.defines = ['HELLO{name}DEFINE="Debug"',
                                       'HELLO{name}BUILD="Debug"']
        self.cpp_info.relwithdebinfo.defines = ['HELLO{name}DEFINE="RelWithDebInfo"',
                                                'HELLO{name}BUILD="RelWithDebInfo"']
        self.cpp_info.minsizerel.defines = ['HELLO{name}DEFINE="MinSizeRel"',
                                            'HELLO{name}BUILD="MinSizeRel"']
"""

testconanfile = """
from conans import ConanFile, CMake
import platform, os, shutil

class TestConan(ConanFile):
    requires = "{name}/0.1@lasote/stable"
    settings = "os", "compiler", "arch"
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        if cmake.is_multi_configuration:
            cmd = 'cmake "%s" %s' % (self.source_folder, cmake.command_line)
            self.run(cmd)
            self.run("cmake --build . --config Debug")
            self.run("cmake --build . --config Release")
        else:
            for config in ("Debug", "Release"):
                self.output.info("Building %s" % config)
                self.run('cmake "%s" %s -DCMAKE_BUILD_TYPE=%s'
                         % (self.source_folder, cmake.command_line, config))
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
cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)

include(${{CMAKE_BINARY_DIR}}/conanbuildinfo.cmake)
conan_basic_setup()

add_library(hello{name} hello.cpp)
set_target_properties(hello{name} PROPERTIES DEBUG_POSTFIX _d)
set_target_properties(hello{name} PROPERTIES MINSIZEREL_POSTFIX _minsizerel)
set_target_properties(hello{name} PROPERTIES RELWITHDEBINFO_POSTFIX _relwithdebinfo)
conan_target_link_libraries(hello{name})
add_executable(say_hello main.cpp)
set_target_properties(say_hello PROPERTIES DEBUG_POSTFIX _d)
set_target_properties(hello{name} PROPERTIES MINSIZEREL_POSTFIX _minsizerel)
set_target_properties(hello{name} PROPERTIES RELWITHDEBINFO_POSTFIX _relwithdebinfo)
target_link_libraries(say_hello hello{name})

"""
testcmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)

include(${{CMAKE_BINARY_DIR}}/conanbuildinfo.cmake)
conan_basic_setup()

add_executable(example main.cpp)
set_target_properties(example PROPERTIES DEBUG_POSTFIX _d)
conan_target_link_libraries(example)

"""


def multi_config_files(name, test=True, deps=None):
    requires = ", ".join(['"%s/0.1@lasote/stable"' % r for r in deps or []])
    requires = requires or "None"
    includes = "\n".join(['#include "hello%s.h"' % d for d in deps or []])
    other_calls = "\n".join(['hello%s();' % d for d in deps or []])

    files = {"conanfile.py": conanfile.format(name=name, requires=requires),
             "CMakeLists.txt": cmake.format(name=name),
             "main.cpp": main.format(name=name),
             "hello.cpp": hello_cpp.format(name=name, includes=includes,
                                           other_calls=other_calls),
             "hello%s.h" % name: hello_h.format(name=name)}
    if test:
        files.update({"test_package/conanfile.py": testconanfile.format(name=name),
                      "test_package/CMakeLists.txt": testcmake.format(name=name),
                      "test_package/main.cpp": main.format(name=name)})

    return files
