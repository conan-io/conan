import unittest
from conans.test.utils.tools import TestClient
import os
from conans.util.files import load
import re
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
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

    def basic_test(self):
        client = TestClient()
        base_folder = client.current_folder
        project = """HelloB:
    folder: ../B
HelloC:
    folder: ../C
"""
        client.save({"C/conanfile.py": conanfile.format(deps=None),
                     "C/header_c.h": "header-c!",
                     "B/conanfile.py": conanfile.format(deps="'HelloC/0.1@lasote/stable'"),
                     "B/header_b.h": "header-b!",
                     "A/conanfile.py": conanfile.format(deps="'HelloB/0.1@lasote/stable'"),
                     "A/conan-project.yml": project})

        client.current_folder = os.path.join(base_folder, "A")
        error = client.run("install . --build=never", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Missing prebuilt package for 'HelloC/0.1@lasote/stable'",
                      client.out)

        client.run("install . -g cmake")
        self.assertIn("HelloC/0.1@lasote/stable: Calling build()", client.out)
        self.assertIn("HelloB/0.1@lasote/stable: Calling build()", client.out)
        # It doesn't build again
        client.run("install . -g cmake --build=never")
        self.assertNotIn("Calling build()", client.out)
        self.assertIn("Not building local package as specified by --build=never", client.out)

        client.run("search")
        self.assertIn("There are no packages", client.out)
        # Check A
        content = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        include_dirs_hellob = re.search('set\(CONAN_INCLUDE_DIRS_HELLOB "(.*)"\)', content).group(1)
        self.assertEqual(include_dirs_hellob,
                         os.path.join(base_folder, "B", "package", "include").replace("\\", "/"))
        self.assertEqual("header-b!", load(os.path.join(include_dirs_hellob, "header_b.h")))
        include_dirs_helloc = re.search('set\(CONAN_INCLUDE_DIRS_HELLOC "(.*)"\)', content).group(1)
        self.assertEqual(include_dirs_helloc,
                         os.path.join(base_folder, "C", "package", "include").replace("\\", "/"))
        self.assertEqual("header-c!", load(os.path.join(include_dirs_helloc, "header_c.h")))

        # Check B
        content = load(os.path.join(base_folder, "B/build/conanbuildinfo.cmake"))
        include_dirs_helloc2 = re.search('set\(CONAN_INCLUDE_DIRS_HELLOC "(.*)"\)', content).group(1)
        self.assertEqual(include_dirs_helloc2, include_dirs_helloc)

        # modify
        client.save({"C/header_c.h": "header-c2!",
                     "B/header_b.h": "header-b2!"})

    def build_test(self):
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
    build: build
    libdirs: build/{build_type}
HelloC:
    folder: C
    includedirs: src
    cmakedir: src
    build: build
    libdirs: build/{build_type}
HelloA:
    folder: A
    cmakedir: src
    build: build

generator: cmake
name: MyProject
"""
        client.save({CONAN_PROJECT: project})

        base_folder = client.current_folder
        client.current_folder = os.path.join(base_folder, "A")
        client.run("install . -if=build")
        self.assertIn("PROJECT: Generated conaninfo.txt", client.out)

        # Make sure nothing in local cache
        client.run("search")
        self.assertIn("There are no packages", client.out)

        # Check A
        content = load(os.path.join(client.current_folder, "build/conanbuildinfo.cmake"))
        include_dirs_hellob = re.search('set\(CONAN_INCLUDE_DIRS_HELLOB "(.*)"\)', content).group(1)
        self.assertIn("void helloB();", load(os.path.join(include_dirs_hellob, "helloB.h")))
        include_dirs_helloc = re.search('set\(CONAN_INCLUDE_DIRS_HELLOC "(.*)"\)', content).group(1)
        self.assertIn("void helloC();", load(os.path.join(include_dirs_helloc, "helloC.h")))

        # Check B
        content = load(os.path.join(base_folder, "B/build/conanbuildinfo.cmake"))
        include_dirs_helloc2 = re.search('set\(CONAN_INCLUDE_DIRS_HELLOC "(.*)"\)', content).group(1)
        self.assertEqual(include_dirs_helloc2, include_dirs_helloc)

        client.run("build . -bf=build")
        command = os.sep.join([".", "build", "Release", "app"])
        client.runner(command, cwd=client.current_folder)
        self.assertIn("Hello World C Release!", client.out)
        self.assertIn("Hello World B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)

        # Now do the same for debug
        client.run("install . -if=build -s build_type=Debug")
        self.assertIn("PROJECT: Generated conaninfo.txt", client.out)
        client.run("build . -bf=build")
        command = os.sep.join([".", "build", "Debug", "app"])
        client.runner(command, cwd=client.current_folder)
        self.assertIn("Hello World C Debug!", client.out)
        self.assertIn("Hello World B Debug!", client.out)
        self.assertIn("Hello World A Debug!", client.out)

        print client.current_folder
        # Now do the same for release
        client.run("install . -if=build -s build_type=Release")
        self.assertIn("PROJECT: Generated conaninfo.txt", client.out)
        client.run("build . -bf=build")
        command = os.sep.join([".", "build", "Release", "app"])
        client.runner(command, cwd=client.current_folder)
        self.assertIn("Hello World C Release!", client.out)
        self.assertIn("Hello World B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)

        client.current_folder = base_folder
        client.runner('cmake . -G "Visual Studio 15 Win64"', cwd=base_folder)
        client.runner('cmake --build . --config Release', cwd=base_folder)
        command = os.sep.join([".", "A", "build", "Release", "app"])
        client.runner(command, cwd=client.current_folder)
        self.assertIn("Hello World C Release!", client.out)
        self.assertIn("Hello World B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)

        tools.replace_in_file(os.path.join(base_folder, "C/src/hello.cpp"),
                              "Hello World", "Bye Moon")
        tools.replace_in_file(os.path.join(base_folder, "B/src/hello.cpp"),
                              "Hello World", "Bye Moon")
        client.runner('cmake --build . --config Release', cwd=base_folder)
        command = os.sep.join([".", "A", "build", "Release", "app"])
        client.runner(command, cwd=client.current_folder)
        self.assertIn("Bye Moon C Release!", client.out)
        self.assertIn("Bye Moon B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)
        client.runner('cmake --build . --config Debug', cwd=base_folder)
        command = os.sep.join([".", "A", "build", "Debug", "app"])
        client.runner(command, cwd=client.current_folder)
        self.assertIn("Bye Moon C Debug!", client.out)
        self.assertIn("Bye Moon B Debug!", client.out)
        self.assertIn("Hello World A Debug!", client.out)

        client.current_folder = base_folder
        client.run("create C HelloC/0.1@lasote/stable")
        client.run("create B HelloB/0.1@lasote/stable")
        client.run("create A HelloA/0.1@lasote/stable")

    def build_cmake_test(self):
        client = TestClient()
        c_files = cpp_hello_conan_files(name="HelloC", settings='"os", "compiler", "arch", "build_type"')
        client.save(c_files, path=os.path.join(client.current_folder, "C"))
        b_files = cpp_hello_conan_files(name="HelloB", deps=["HelloC/0.1@lasote/stable"],
                                        settings='"os", "compiler", "arch", "build_type"')
        client.save(b_files, path=os.path.join(client.current_folder, "B"))

        base_folder = client.current_folder
        project = """HelloB:
    folder: B
    includedirs: .
    build: build_{build_type}_{arch}
    libdirs: build_{build_type}_{arch}/lib
HelloC:
    folder: C
    includedirs: .
    build: build_{build_type}_{arch}
    libdirs: build_{build_type}_{arch}/lib
HelloA:
    folder: A

generator: cmake
name: MyProject
"""
        a_files = cpp_hello_conan_files(name="HelloA", deps=["HelloB/0.1@lasote/stable"],
                                        settings='"os", "compiler", "arch", "build_type"')
        client.save(a_files, path=os.path.join(client.current_folder, "A"))
        client.save({CONAN_PROJECT: project})

        client.current_folder = os.path.join(base_folder, "A")
        client.run("install . -g cmake --build")
        print client.out

        # Check A
        content = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))

        include_dirs_hellob = re.search('set\(CONAN_INCLUDE_DIRS_HELLOB "(.*)"\)', content).group(1)
        self.assertIn("void helloHelloB();", load(os.path.join(include_dirs_hellob, "helloHelloB.h")))
        include_dirs_helloc = re.search('set\(CONAN_INCLUDE_DIRS_HELLOC "(.*)"\)', content).group(1)
        self.assertIn("void helloHelloC();", load(os.path.join(include_dirs_helloc, "helloHelloC.h")))

        # Check B
        content = load(os.path.join(base_folder, "B/build_Release_x86_64/conanbuildinfo.cmake"))
        include_dirs_helloc2 = re.search('set\(CONAN_INCLUDE_DIRS_HELLOC "(.*)"\)', content).group(1)
        self.assertEqual(include_dirs_helloc2, include_dirs_helloc)

        client.run("build .")
        print "CURRENT FOLDER ", client.current_folder
        print client.out
        command = os.sep.join([".", "bin", "say_hello"])
        client.runner(command, cwd=client.current_folder)
        print client.current_folder
        print client.out
        self.assertIn("Hello HelloA", client.out)
        self.assertIn("Hello HelloB", client.out)
        self.assertIn("Hello HelloC", client.out)

        print load(os.path.join(base_folder, "CMakeLists.txt"))

    def basic_test2(self):
        client = TestClient()
        base_folder = client.current_folder
        cache_folder = os.path.join(client.client_cache.conan_folder, "data").replace("\\", "/")

        for pkg in "A", "B", "C", "D", "E":
            deps = ["Hello%s/0.1@lasote/stable" % (chr(ord(pkg)+1))] if pkg != "E" else None
            deps = ", ".join('"%s"' % d for d in deps) if deps else "None"
            files = {"conanfile.py": conanfile.format(deps=deps)}
            client.save(files, path=os.path.join(base_folder, pkg))
        for pkg in reversed(["B", "C", "D", "E"]):
            client.run("create %s Hello%s/0.1@lasote/stable" % (pkg, pkg))

        client.current_folder = os.path.join(base_folder, "A")
        client.run("install . -g cmake")
        content = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        content = content.replace(cache_folder, "")

        self.assertIn('set(CONAN_HELLOB_ROOT "/HelloB/0.1/lasote/stable/package/'
                      '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")',
                      content)
        self.assertIn('set(CONAN_HELLOC_ROOT "/HelloC/0.1/lasote/stable/package/'
                      '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")',
                      content)
        self.assertIn('set(CONAN_HELLOD_ROOT "/HelloD/0.1/lasote/stable/package/'
                      '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")',
                      content)
        self.assertIn('set(CONAN_HELLOE_ROOT "/HelloE/0.1/lasote/stable/package/'
                      '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")',
                      content)

        client.save({"conan-project.txt": """[HelloC]
folder: %s""" % os.path.join(base_folder, "C")})
        client.run("install . -g cmake")
        content = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        content = content.replace(cache_folder, "")

        self.assertIn('set(CONAN_HELLOB_ROOT "/HelloB/0.1/lasote/stable/package/'
                      '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")',
                      content)

        root_folder = re.search('set\(CONAN_HELLOC_ROOT "(.*)"\)', content).group(1)
        self.assertIn('set(CONAN_HELLOC_ROOT "%s")' % root_folder,
                      content)
        self.assertIn('set(CONAN_HELLOD_ROOT "/HelloD/0.1/lasote/stable/package/'
                      '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")',
                      content)
        self.assertIn('set(CONAN_HELLOE_ROOT "/HelloE/0.1/lasote/stable/package/'
                      '5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")',
                      content)
