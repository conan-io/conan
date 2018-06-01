import unittest
import os
import platform

from conans.test.utils.tools import TestClient
from conans.model.project import CONAN_PROJECT
from conans import tools


conanfile = """from conans import ConanFile
import os
class Pkg(ConanFile):
    requires = {deps}
    generators = "cmake"
    exports_sources = "*.h"
    def build(self):
        assert os.path.exists("conanbuildinfo.cmake")
    def package(self):
        self.copy("*.h", dst="include")
    def package_id(self):
        self.info.header_only()
"""

conanfile_build = """from conans import ConanFile, CMake
class Pkg(ConanFile):
    settings = "os", "compiler", "arch", "build_type"
    requires = {deps}
    generators = "cmake"
    exports_sources = "src/*"

    def build(self):
        cmake = CMake(self)
        cmake.configure(source_folder="src")
        cmake.build()

    def package(self):
        self.copy("*.h", src="src", dst="include")
        self.copy("*.lib", dst="lib", keep_path=False)
        self.copy("*.a", dst="lib", keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["hello{name}"]
"""

hello_cpp = """#include <iostream>
#include "hello{name}.h"
{includes}
void hello{name}(){{
    {calls}
    #ifdef NDEBUG
    std::cout << "Hello World {name} Release!" <<std::endl;
    #else
    std::cout << "Hello World {name} Debug!" <<std::endl;
    #endif
}}
"""

main_cpp = """#include "helloA.h"
int main(){
    helloA();
}
"""

hello_h = """#pragma once
#ifdef WIN32
  #define HELLO_EXPORT __declspec(dllexport)
#else
  #define HELLO_EXPORT
#endif
HELLO_EXPORT void hello{name}();
"""

cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
project(Hello CXX)
cmake_minimum_required(VERSION 2.8.12)
include(${{CMAKE_CURRENT_BINARY_DIR}}/conanbuildinfo.cmake)
conan_basic_setup(NO_OUTPUT_DIRS)
add_library(hello{name} hello.cpp)
target_link_libraries(hello{name} ${{CONAN_LIBS}})
"""


class ConanProjectTest(unittest.TestCase):

    def outsource_build_test(self):
        client = TestClient()

        def files(name, depend=None):
            includes = ('#include "hello%s.h"' % depend) if depend else ""
            calls = ('hello%s();' % depend) if depend else ""
            deps = ('"Hello%s/0.1@lasote/stable"' % depend) if depend else "None"
            return {"conanfile.py": conanfile_build.format(deps=deps, name=name),
                    "src/hello%s.h" % name: hello_h.format(name=name),
                    "src/hello.cpp": hello_cpp.format(name=name, includes=includes, calls=calls),
                    "src/CMakeLists.txt": cmake.format(name=name)}

        client.save(files("C"), path=os.path.join(client.current_folder, "C"))
        client.save(files("B", "C"), path=os.path.join(client.current_folder, "B"))
        a = files("A", "B")
        a["src/CMakeLists.txt"] += "add_executable(app main.cpp)\ntarget_link_libraries(app helloA)\n"
        a["src/main.cpp"] = main_cpp
        client.save(a, path=os.path.join(client.current_folder, "A"))

        project = """HelloB:
    folder: B
    includedirs: src
    cmakedir: src
HelloC:
    folder: C
    includedirs: src
    cmakedir: src
HelloA:
    folder: A
    cmakedir: src

root: HelloA
generator: cmake
name: MyProject
"""
        client.save({CONAN_PROJECT: project})
        client.run("install . -if=build")
        generator = "Visual Studio 15 Win64" if platform.system() == "Windows" else "Unix Makefiles"
        base_folder = os.path.join(client.current_folder, "build")
        client.runner('cmake .. -G "%s" -DCMAKE_BUILD_TYPE=Release' % generator, cwd=base_folder)
        client.runner('cmake --build . --config Release', cwd=base_folder)
        if platform.system() == "Windows":
            cmd_release = r".\build\A\Release\app"
            cmd_debug = r".\build\A\Debug\app"
        else:
            cmd_release = "./A/app"
            cmd_debug = "./A/app"

        client.runner(cmd_release, cwd=client.current_folder)
        self.assertIn("Hello World C Release!", client.out)
        self.assertIn("Hello World B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)
        tools.replace_in_file(os.path.join(client.current_folder, "C/src/hello.cpp"),
                              "Hello World", "Bye Moon")
        tools.replace_in_file(os.path.join(client.current_folder, "B/src/hello.cpp"),
                              "Hello World", "Bye Moon")
        client.runner('cmake --build . --config Release', cwd=base_folder)
        client.runner(cmd_release, cwd=client.current_folder)
        self.assertIn("Bye Moon C Release!", client.out)
        self.assertIn("Bye Moon B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)

        client.runner('cmake .. -G "%s" -DCMAKE_BUILD_TYPE=Debug' % generator, cwd=base_folder)
        client.runner('cmake --build . --config Debug', cwd=base_folder)
        client.runner(cmd_debug, cwd=client.current_folder)
        self.assertIn("Bye Moon C Debug!", client.out)
        self.assertIn("Bye Moon B Debug!", client.out)
        self.assertIn("Hello World A Debug!", client.out)

        tools.replace_in_file(os.path.join(client.current_folder, "B/src/hello.cpp"),
                              "Bye Moon", "Bye! Mars")
        client.runner('cmake --build . --config Debug', cwd=base_folder)
        client.runner(cmd_debug, cwd=client.current_folder)
        self.assertIn("Bye Moon C Debug!", client.out)
        self.assertIn("Bye! Mars B Debug!", client.out)
        self.assertIn("Hello World A Debug!", client.out)
