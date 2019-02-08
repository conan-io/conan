import os
import platform
import unittest
from textwrap import dedent

from conans.client import tools
from conans.test.utils.tools import TestClient
from conans.util.files import load
import time


conanfile_build = """from conans import ConanFile, CMake
class Pkg(ConanFile):
    settings = "os", "compiler", "arch", "build_type"
    requires = {deps}
    generators = "cmake", "cmake_multi"
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
conan_basic_setup()
add_library(hello{name} hello.cpp)
target_link_libraries(hello{name} ${{CONAN_LIBS}})
"""

cmake_multi = """set(CMAKE_CXX_COMPILER_WORKS 1)
project(Hello CXX)
cmake_minimum_required(VERSION 2.8.12)
include(${{CMAKE_CURRENT_BINARY_DIR}}/conanbuildinfo_multi.cmake)
conan_basic_setup()
add_library(hello{name} hello.cpp)
conan_target_link_libraries(hello{name})
"""

cmake_targets = """set(CMAKE_CXX_COMPILER_WORKS 1)
project(Hello CXX)
cmake_minimum_required(VERSION 2.8.12)
include(${{CMAKE_CURRENT_BINARY_DIR}}/conanbuildinfo.cmake)
conan_basic_setup(TARGETS)
add_library(hello{name} hello.cpp)
target_link_libraries(hello{name} {dep})
"""


class WorkspaceTest(unittest.TestCase):
    def simple_test(self):
        client = TestClient()

        def files(name, depend=None):
            deps = ('"Hello%s/0.1@lasote/stable"' % depend) if depend else "None"
            return {"conanfile.py": conanfile_build.format(deps=deps, name=name)}

        client.save(files("C"), path=os.path.join(client.current_folder, "C"))
        client.save(files("B", "C"), path=os.path.join(client.current_folder, "B"))
        client.save(files("A", "B"), path=os.path.join(client.current_folder, "A"))

        project = dedent("""
                            HelloB/0.1@lasote/stable:
                                folder: B
                            HelloC/0.1@lasote/stable:
                                folder: C
                            HelloA/0.1@lasote/stable:
                                folder: A
                            layout: layout
                            root: HelloA/0.1@lasote/stable
                          """)
        layout = dedent("""
                        [folders]
                        build:
                        """)
        client.save({"conanws.yml": project,
                     "layout": layout})
        client.run("workspace install conanws.yml")
        self.assertIn("HelloA/0.1@lasote/stable from user folder - Editable", client.out)
        self.assertIn("HelloB/0.1@lasote/stable from user folder - Editable", client.out)
        self.assertIn("HelloC/0.1@lasote/stable from user folder - Editable", client.out)
        for sub in ("A", "B", "C"):
            for f in ("conanbuildinfo.cmake", "conaninfo.txt", "conanbuildinfo.txt"):
                self.assertTrue(os.path.exists(os.path.join(client.current_folder, sub, f)))

    def simple_build_test(self):
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
        A = os.path.join(client.current_folder, "A")
        a = files("A", "B")
        a["src/CMakeLists.txt"] += ("add_executable(app main.cpp)\n"
                                    "target_link_libraries(app helloA)\n")
        a["src/main.cpp"] = main_cpp
        client.save(a, path=A)

        project = dedent("""
                        HelloB/0.1@lasote/stable:
                            folder: B
                        HelloC/0.1@lasote/stable:
                            folder: C
                        HelloA/0.1@lasote/stable:
                            folder: A
                        layout: layout
                        root: HelloA/0.1@lasote/stable
                      """)
        layout = dedent("""
                        [folders]
                        build: build/{settings.build_type}

                        [includedirs]
                        src

                        [libdirs]
                        build/{settings.build_type}/lib
                        """)
        client.save({"conanws.yml": project,
                     "layout": layout})
        client.run("workspace install conanws.yml")
        client.run("workspace install conanws.yml -s build_type=Debug")
        self.assertIn("HelloA/0.1@lasote/stable from user folder - Editable", client.out)
        self.assertIn("HelloB/0.1@lasote/stable from user folder - Editable", client.out)
        self.assertIn("HelloC/0.1@lasote/stable from user folder - Editable", client.out)

        build_type = "Release"
        client.run("build C -bf=C/build/%s" % build_type)
        client.run("build B -bf=B/build/%s" % build_type)
        client.run("build A -bf=A/build/%s" % build_type)

        cmd_release = os.path.normpath("./A/build/Release/bin/app")
        cmd_debug = os.path.normpath("./A/build/Debug/bin/app")

        client.runner(cmd_release, cwd=client.current_folder)
        self.assertIn("Hello World C Release!", client.out)
        self.assertIn("Hello World B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)

        build_type = "Debug"
        client.run("build C -bf=C/build/%s" % build_type)
        client.run("build B -bf=B/build/%s" % build_type)
        client.run("build A -bf=A/build/%s" % build_type)

        client.runner(cmd_debug, cwd=client.current_folder)
        self.assertIn("Hello World C Debug!", client.out)
        self.assertIn("Hello World B Debug!", client.out)
        self.assertIn("Hello World A Debug!", client.out)

    def complete_single_conf_build_test(self):
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
        A = os.path.join(client.current_folder, "A")
        a = files("A", "B")
        a["src/CMakeLists.txt"] += ("add_executable(app main.cpp)\n"
                                    "target_link_libraries(app helloA)\n")
        a["src/main.cpp"] = main_cpp
        client.save(a, path=A)

        project = dedent("""
                        HelloB/0.1@lasote/stable:
                            folder: B
                        HelloC/0.1@lasote/stable:
                            folder: C
                        HelloA/0.1@lasote/stable:
                            folder: A
                        layout: layout
                        generator: cmake
                        root: HelloA/0.1@lasote/stable
                      """)
        layout = dedent("""
                        [folders]
                        build: build/{settings.build_type}
                        src: src

                        [includedirs]
                        src

                        [libdirs]
                        build/{settings.build_type}/lib
                        """)
        metacmake = dedent("""
                        cmake_minimum_required(VERSION 3.3)
                        project(MyProject CXX)
                        include(${CMAKE_BINARY_DIR}/conanworkspace.cmake)
        """)
        client.save({"conanws.yml": project,
                     "layout": layout,
                     "CMakeLists.txt": metacmake})

        base_release = os.path.join(client.current_folder, "build_release")
        base_debug = os.path.join(client.current_folder, "build_debug")

        with client.chdir("build_release"):
            client.run("workspace install ../conanws.yml")
        with client.chdir("build_debug"):
            client.run("workspace install ../conanws.yml -s build_type=Debug")

        generator = "Visual Studio 15 Win64" if platform.system() == "Windows" else "Unix Makefiles"
        client.runner('cmake .. -G "%s" -DCMAKE_BUILD_TYPE=Release' % generator, cwd=base_release)
        client.runner('cmake --build . --config Release', cwd=base_release)

        cmd_release = os.path.normpath("./A/build/Release/bin/app")
        cmd_debug = os.path.normpath("./A/build/Debug/bin/app")

        client.runner(cmd_release, cwd=client.current_folder)
        self.assertIn("Hello World C Release!", client.out)
        self.assertIn("Hello World B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)

        tools.replace_in_file(os.path.join(client.current_folder, "C/src/hello.cpp"),
                              "Hello World", "Bye Moon", output=client.out)

        client.runner('cmake --build . --config Release', cwd=base_release)
        client.runner(cmd_release, cwd=client.current_folder)
        self.assertIn("Bye Moon C Release!", client.out)
        self.assertIn("Hello World B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)

        time.sleep(1)
        tools.replace_in_file(os.path.join(client.current_folder, "B/src/hello.cpp"),
                              "Hello World", "Bye Moon", output=client.out)
        time.sleep(1)
        client.runner('cmake --build . --config Release', cwd=base_release)
        client.runner(cmd_release, cwd=client.current_folder)
        self.assertIn("Bye Moon C Release!", client.out)
        self.assertIn("Bye Moon B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)

        client.runner('cmake .. -G "%s" -DCMAKE_BUILD_TYPE=Debug' % generator, cwd=base_debug)
        client.runner('cmake --build . --config Debug', cwd=base_debug)
        client.runner(cmd_debug, cwd=client.current_folder)
        self.assertIn("Bye Moon C Debug!", client.out)
        self.assertIn("Bye Moon B Debug!", client.out)
        self.assertIn("Hello World A Debug!", client.out)

        time.sleep(1)
        tools.replace_in_file(os.path.join(client.current_folder, "C/src/hello.cpp"),
                              "Bye Moon", "Hello World", output=client.out)

        time.sleep(1)
        client.runner('cmake --build . --config Debug', cwd=base_debug)
        client.runner(cmd_debug, cwd=client.current_folder)
        self.assertIn("Hello World C Debug!", client.out)
        self.assertIn("Bye Moon B Debug!", client.out)
        self.assertIn("Hello World A Debug!", client.out)

    @unittest.skipUnless(platform.system() == "Windows", "only windows")
    def complete_multi_conf_build_test(self):
        client = TestClient()

        def files(name, depend=None):
            includes = ('#include "hello%s.h"' % depend) if depend else ""
            calls = ('hello%s();' % depend) if depend else ""
            deps = ('"Hello%s/0.1@lasote/stable"' % depend) if depend else "None"
            return {"conanfile.py": conanfile_build.format(deps=deps, name=name),
                    "src/hello%s.h" % name: hello_h.format(name=name),
                    "src/hello.cpp": hello_cpp.format(name=name, includes=includes, calls=calls),
                    "src/CMakeLists.txt": cmake_multi.format(name=name)}

        client.save(files("C"), path=os.path.join(client.current_folder, "C"))
        client.save(files("B", "C"), path=os.path.join(client.current_folder, "B"))
        A = os.path.join(client.current_folder, "A")
        a = files("A", "B")
        a["src/CMakeLists.txt"] += ("add_executable(app main.cpp)\n"
                                    "target_link_libraries(app helloA)\n")
        a["src/main.cpp"] = main_cpp
        client.save(a, path=A)

        project = dedent("""
                        HelloB/0.1@lasote/stable:
                            folder: B
                        HelloC/0.1@lasote/stable:
                            folder: C
                        HelloA/0.1@lasote/stable:
                            folder: A
                        layout: layout
                        generator: cmake
                        root: HelloA/0.1@lasote/stable
                      """)
        layout = dedent("""
                        [folders]
                        build: build
                        src: src

                        [includedirs]
                        src

                        [libdirs]
                        build/{settings.build_type}
                        """)
        metacmake = dedent("""
                        cmake_minimum_required(VERSION 3.3)
                        project(MyProject CXX)
                        include(${CMAKE_BINARY_DIR}/conanworkspace.cmake)
        """)
        client.save({"conanws.yml": project,
                     "layout": layout,
                     "CMakeLists.txt": metacmake})

        build = os.path.join(client.current_folder, "build")

        with client.chdir("build"):
            client.run("workspace install ../conanws.yml")
            client.run("workspace install ../conanws.yml -s build_type=Debug")

        generator = "Visual Studio 15 Win64"
        client.runner('cmake .. -G "%s" -DCMAKE_BUILD_TYPE=Release' % generator, cwd=build)
        client.runner('cmake --build . --config Release', cwd=build)

        cmd_release = os.path.normpath("./A/build/Release/app")
        cmd_debug = os.path.normpath("./A/build/Debug/app")

        client.runner(cmd_release, cwd=client.current_folder)
        self.assertIn("Hello World C Release!", client.out)
        self.assertIn("Hello World B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)

        tools.replace_in_file(os.path.join(client.current_folder, "C/src/hello.cpp"),
                              "Hello World", "Bye Moon", output=client.out)

        client.runner('cmake --build . --config Release', cwd=build)
        client.runner(cmd_release, cwd=client.current_folder)
        self.assertIn("Bye Moon C Release!", client.out)
        self.assertIn("Hello World B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)

        tools.replace_in_file(os.path.join(client.current_folder, "B/src/hello.cpp"),
                              "Hello World", "Bye Moon", output=client.out)

        client.runner('cmake --build . --config Release', cwd=build)
        client.runner(cmd_release, cwd=client.current_folder)
        self.assertIn("Bye Moon C Release!", client.out)
        self.assertIn("Bye Moon B Release!", client.out)
        self.assertIn("Hello World A Release!", client.out)

        client.runner('cmake .. -G "%s" -DCMAKE_BUILD_TYPE=Debug' % generator, cwd=build)
        client.runner('cmake --build . --config Debug', cwd=build)
        client.runner(cmd_debug, cwd=client.current_folder)
        self.assertIn("Bye Moon C Debug!", client.out)
        self.assertIn("Bye Moon B Debug!", client.out)
        self.assertIn("Hello World A Debug!", client.out)

        tools.replace_in_file(os.path.join(client.current_folder, "C/src/hello.cpp"),
                              "Bye Moon", "Hello World", output=client.out)

        client.runner('cmake --build . --config Debug', cwd=build)
        client.runner(cmd_debug, cwd=client.current_folder)
        self.assertIn("Hello World C Debug!", client.out)
        self.assertIn("Bye Moon B Debug!", client.out)
        self.assertIn("Hello World A Debug!", client.out)

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

        project = dedent("""
            HelloB/0.1@lasote/stable:
                folder: B
            HelloC/0.1@lasote/stable:
                folder: C
            HelloA/0.1@lasote/stable:
                folder: A
            layout: layout
            root: HelloA/0.1@lasote/stable
            """)
        layout = dedent("""
                        [folders]
                        build: build
                        """)
        client.save({"conanws.yml": project,
                     "layout": layout})

        client.run("workspace install conanws.yml")
        self.assertIn("HelloC/0.1@lasote/stable: Applying build-requirement: Tool/0.1@user/testing",
                      client.out)
        self.assertIn("HelloB/0.1@lasote/stable: Applying build-requirement: Tool/0.1@user/testing",
                      client.out)
        self.assertIn("HelloA/0.1@lasote/stable: Applying build-requirement: Tool/0.1@user/testing",
                      client.out)
        for sub in ("A", "B", "C"):
            conanbuildinfo = load(os.path.join(client.current_folder, sub, "build",
                                               "conanbuildinfo.cmake"))
            self.assertIn("set(CONAN_LIBS_TOOL MyToolLib)", conanbuildinfo)
