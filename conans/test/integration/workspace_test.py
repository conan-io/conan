import unittest
import os
import platform
import shutil

from parameterized.parameterized import parameterized

from conans.test.utils.tools import TestClient
from conans.model.workspace import WORKSPACE_FILE
from conans import tools
import time
from conans.util.files import load
import re


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

cmake_targets = """set(CMAKE_CXX_COMPILER_WORKS 1)
project(Hello CXX)
cmake_minimum_required(VERSION 2.8.12)
include(${{CMAKE_CURRENT_BINARY_DIR}}/conanbuildinfo.cmake)
conan_basic_setup(NO_OUTPUT_DIRS TARGETS)
add_library(hello{name} hello.cpp)
target_link_libraries(hello{name} {dep})
"""


class WorkspaceTest(unittest.TestCase):

    def build_requires_test(self):
        # https://github.com/conan-io/conan/issues/3075
        client = TestClient()
        tool = """from conans import ConanFile
class Tool(ConanFile):
    def package_info(self):
        self.cpp_info.libs = ["MyToolLib"]
"""
        client.save({"conanfile.py": tool})
        client.run("create . Tool/0.1@user/testing")

        conanfile = """from conans import ConanFile
import os
class Pkg(ConanFile):
    requires = {deps}
    build_requires = "Tool/0.1@user/testing"
    generators = "cmake"
"""

        def files(name, depend=None):
            deps = ('"Hello%s/0.1@lasote/stable"' % depend) if depend else "None"
            return {"conanfile.py": conanfile.format(deps=deps, name=name)}

        client.save(files("C"), path=os.path.join(client.current_folder, "C"))
        client.save(files("B", "C"), path=os.path.join(client.current_folder, "B"))
        client.save(files("A", "B"), path=os.path.join(client.current_folder, "A"))

        project = """HelloB:
    folder: B
HelloC:
    folder: C
HelloA:
    folder: A

root: HelloA
"""
        client.save({WORKSPACE_FILE: project})
        client.run("install . -if=build")
        self.assertIn("Workspace HelloC: Applying build-requirement: Tool/0.1@user/testing",
                      client.out)
        self.assertIn("Workspace HelloB: Applying build-requirement: Tool/0.1@user/testing",
                      client.out)
        self.assertIn("Workspace HelloA: Applying build-requirement: Tool/0.1@user/testing",
                      client.out)
        for sub in ("A", "B", "C"):
            conanbuildinfo = load(os.path.join(client.current_folder, "build", sub, "conanbuildinfo.cmake"))
            self.assertIn("set(CONAN_LIBS_TOOL MyToolLib)", conanbuildinfo)

    @parameterized.expand([(True, ), (False, )])
    # @unittest.skipUnless(platform.system() in ("Windows", "Linux"), "Test doesn't work on OSX")
    def cmake_outsource_build_test(self, targets):
        client = TestClient()

        def files(name, depend=None):
            includes = ('#include "hello%s.h"' % depend) if depend else ""
            calls = ('hello%s();' % depend) if depend else ""
            deps = ('"Hello%s/0.1@lasote/stable"' % depend) if depend else "None"
            dep = "CONAN_PKG::Hello%s" % depend if depend else ""
            used_cmake = cmake_targets.format(dep=dep, name=name) if targets else cmake.format(name=name)
            return {"conanfile.py": conanfile_build.format(deps=deps, name=name),
                    "src/hello%s.h" % name: hello_h.format(name=name),
                    "src/hello.cpp": hello_cpp.format(name=name, includes=includes, calls=calls),
                    "src/CMakeLists.txt": used_cmake}

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
        client.save({WORKSPACE_FILE: project})
        client.run("install . -if=build")
        generator = "Visual Studio 15 Win64" if platform.system() == "Windows" else "Unix Makefiles"
        base_folder = os.path.join(client.current_folder, "build")
        client.runner('cmake .. -G "%s" -DCMAKE_BUILD_TYPE=Release' % generator, cwd=base_folder)
        client.runner('cmake --build . --config Release', cwd=base_folder)
        if platform.system() == "Windows":
            cmd_release = r".\build\A\Release\app"
            cmd_debug = r".\build\A\Debug\app"
        else:
            cmd_release = "./build/A/app"
            cmd_debug = "./build/A/app"

        client.runner(cmd_release, cwd=client.current_folder)
        self.assertIn("Hello World C Release!", client.out)
        self.assertIn("Hello World B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)
        TIME_DELAY = 1
        time.sleep(TIME_DELAY)
        tools.replace_in_file(os.path.join(client.current_folder, "C/src/hello.cpp"),
                              "Hello World", "Bye Moon")
        tools.replace_in_file(os.path.join(client.current_folder, "B/src/hello.cpp"),
                              "Hello World", "Bye Moon")
        time.sleep(TIME_DELAY)
        client.runner('cmake --build . --config Release', cwd=base_folder)
        time.sleep(TIME_DELAY)
        client.runner(cmd_release, cwd=client.current_folder)
        self.assertIn("Bye Moon C Release!", client.out)
        self.assertIn("Bye Moon B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)

        shutil.rmtree(os.path.join(client.current_folder, "build"))
        client.run("install . -if=build -s build_type=Debug")
        client.runner('cmake .. -G "%s" -DCMAKE_BUILD_TYPE=Debug' % generator, cwd=base_folder)
        time.sleep(TIME_DELAY)
        client.runner('cmake --build . --config Debug', cwd=base_folder)
        time.sleep(TIME_DELAY)
        client.runner(cmd_debug, cwd=client.current_folder)
        self.assertIn("Bye Moon C Debug!", client.out)
        self.assertIn("Bye Moon B Debug!", client.out)
        self.assertIn("Hello World A Debug!", client.out)

        tools.replace_in_file(os.path.join(client.current_folder, "B/src/hello.cpp"),
                              "Bye Moon", "Bye! Mars")
        time.sleep(TIME_DELAY)
        client.runner('cmake --build . --config Debug', cwd=base_folder)
        time.sleep(TIME_DELAY)
        client.runner(cmd_debug, cwd=client.current_folder)
        self.assertIn("Bye Moon C Debug!", client.out)
        self.assertIn("Bye! Mars B Debug!", client.out)
        self.assertIn("Hello World A Debug!", client.out)

    def insource_build_test(self):
        client = TestClient()

        def files(name, depend=None):
            includes = ('#include "hello%s.h"' % depend) if depend else ""
            calls = ('hello%s();' % depend) if depend else ""
            deps = ('"Hello%s/0.1@lasote/stable"' % depend) if depend else "None"
            return {"conanfile.py": conanfile_build.format(deps=deps, name=name),
                    "src/hello%s.h" % name: hello_h.format(name=name),
                    "src/hello.cpp": hello_cpp.format(name=name, includes=includes, calls=calls),
                    "src/CMakeLists.txt": cmake.format(name=name)}

        C = os.path.join(client.current_folder, "C")
        B = os.path.join(client.current_folder, "B")
        A = os.path.join(client.current_folder, "A")
        client.save(files("C"), path=C)
        client.save(files("B", "C"), path=B)
        a = files("A", "B")
        a["src/CMakeLists.txt"] += "add_executable(app main.cpp)\ntarget_link_libraries(app helloA)\n"
        a["src/main.cpp"] = main_cpp
        client.save(a, path=A)

        project = """HelloB:
    folder: B
    includedirs: src
    cmakedir: src
    build: "'build' if '{os}'=='Windows' else 'build_{build_type}'.lower()"
    libdirs: "'build/{build_type}' if '{os}'=='Windows' else 'build_{build_type}'.lower()"
HelloC:
    folder: C
    includedirs: src
    cmakedir: src
    build: "'build' if '{os}'=='Windows' else 'build_{build_type}'.lower()"
    libdirs: "'build/{build_type}' if '{os}'=='Windows' else 'build_{build_type}'.lower()"
HelloA:
    folder: A
    cmakedir: src
    build: "'build' if '{os}'=='Windows' else 'build_{build_type}'.lower()"

root: HelloA
"""
        client.save({WORKSPACE_FILE: project})

        release = "build" if platform.system() == "Windows" else "build_release"
        debug = "build" if platform.system() == "Windows" else "build_debug"

        base_folder = client.current_folder
        client.run("install .")

        # Make sure nothing in local cache
        client.run("search")
        self.assertIn("There are no packages", client.out)

        # Check A
        content = load(os.path.join(client.current_folder, "A/%s/conanbuildinfo.cmake" % release))
        include_dirs_hellob = re.search('set\(CONAN_INCLUDE_DIRS_HELLOB "(.*)"\)', content).group(1)
        self.assertIn("void helloB();", load(os.path.join(include_dirs_hellob, "helloB.h")))
        include_dirs_helloc = re.search('set\(CONAN_INCLUDE_DIRS_HELLOC "(.*)"\)', content).group(1)
        self.assertIn("void helloC();", load(os.path.join(include_dirs_helloc, "helloC.h")))

        # Check B
        content = load(os.path.join(base_folder, "B/%s/conanbuildinfo.cmake" % release))
        include_dirs_helloc2 = re.search('set\(CONAN_INCLUDE_DIRS_HELLOC "(.*)"\)', content).group(1)
        self.assertEqual(include_dirs_helloc2, include_dirs_helloc)

        client.run("build C -bf=C/%s" % release)
        client.run("build B -bf=B/%s" % release)
        client.run("build A -bf=A/%s" % release)
        if platform.system() == "Windows":
            cmd_release = r".\A\build\Release\app"
            cmd_debug = r".\A\build\Debug\app"
        else:
            cmd_release = "./A/build_release/app"
            cmd_debug = "./A/build_debug/app"
        client.runner(cmd_release, cwd=client.current_folder)
        self.assertIn("Hello World C Release!", client.out)
        self.assertIn("Hello World B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)

        # Now do the same for debug
        client.run("install . -s build_type=Debug")
        client.run("build C -bf=C/%s" % debug)
        client.run("build B -bf=B/%s" % debug)
        client.run("build A -bf=A/%s" % debug)
        client.runner(cmd_debug, cwd=client.current_folder)
        self.assertIn("Hello World C Debug!", client.out)
        self.assertIn("Hello World B Debug!", client.out)
        self.assertIn("Hello World A Debug!", client.out)
