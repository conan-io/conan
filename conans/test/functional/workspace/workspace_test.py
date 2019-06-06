import os
import platform
import time
import unittest
from textwrap import dedent

import six
from parameterized.parameterized import parameterized

from conans.client import tools
from conans.errors import ConanException
from conans.model.workspace import Workspace
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import load, save

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

cmake_multi = """set(CMAKE_CXX_COMPILER_WORKS 1)
project(Hello CXX)
cmake_minimum_required(VERSION 2.8.12)
include(${{CMAKE_CURRENT_BINARY_DIR}}/conanbuildinfo_multi.cmake)
conan_basic_setup(TARGETS)
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
            editables:
                HelloB/0.1@lasote/stable:
                    path: B
                HelloC/0.1@lasote/stable:
                    path: C
                HelloA/0.1@lasote/stable:
                    path: A
            layout: layout
            workspace_generator: cmake
            root: HelloA/0.1@lasote/stable
            """)
        layout = dedent("""
            [build_folder]

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

    @parameterized.expand([("csv",), ("list",), (("abbreviated_list"))])
    def multiple_roots_test(self, root_attribute_format):
        # https://github.com/conan-io/conan/issues/4720
        client = TestClient()

        def files(name, depend=None):
            deps = ('"Hello%s/0.1@lasote/stable"' % depend) if depend else "None"
            return {"conanfile.py": conanfile_build.format(deps=deps, name=name)}

        client.save(files("D"), path=os.path.join(client.current_folder, "D"))
        client.save(files("C", "D"), path=os.path.join(client.current_folder, "C"))
        client.save(files("A", "C"), path=os.path.join(client.current_folder, "A"))
        client.save(files("B", "D"), path=os.path.join(client.current_folder, "B"))

        # https://github.com/conan-io/conan/issues/5155
        roots = ["HelloA/0.1@lasote/stable", "HelloB/0.1@lasote/stable"]
        root_attribute = {
            "csv": ", ".join(roots),
            "list": "".join(["\n    - %s" % r for r in roots]),
            "abbreviated_list": str(roots),
        }[root_attribute_format]

        project = dedent("""
            editables:
                HelloD/0.1@lasote/stable:
                    path: D
                HelloB/0.1@lasote/stable:
                    path: B
                HelloC/0.1@lasote/stable:
                    path: C
                HelloA/0.1@lasote/stable:
                    path: A
            workspace_generator: cmake
            layout: layout
            root: {root_attribute}
            """).format(root_attribute=root_attribute)

        layout = dedent("""
            [build_folder]
            """)
        client.save({"conanws.yml": project,
                     "layout": layout})
        client.run("workspace install conanws.yml")
        self.assertIn("HelloA/0.1@lasote/stable from user folder - Editable", client.out)
        self.assertIn("HelloB/0.1@lasote/stable from user folder - Editable", client.out)
        self.assertIn("HelloC/0.1@lasote/stable from user folder - Editable", client.out)
        self.assertIn("HelloD/0.1@lasote/stable from user folder - Editable", client.out)

        a_cmake = load(os.path.join(client.current_folder, "A", "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS helloC helloD ${CONAN_LIBS})", a_cmake)
        b_cmake = load(os.path.join(client.current_folder, "B", "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS helloD ${CONAN_LIBS})", b_cmake)

    def transitivity_test(self):
        # https://github.com/conan-io/conan/issues/4720
        client = TestClient()

        def files(name, depend=None):
            if isinstance(depend, list):
                deps = ", ".join(["'Hello%s/0.1@lasote/stable'" % d for d in depend])
            else:
                deps = ('"Hello%s/0.1@lasote/stable"' % depend) if depend else "None"
            return {"conanfile.py": conanfile_build.format(deps=deps, name=name)}

        client.save(files("D"), path=os.path.join(client.current_folder, "D"))
        client.save(files("C", "D"), path=os.path.join(client.current_folder, "C"))
        client.save(files("B", "C"), path=os.path.join(client.current_folder, "B"))

        client.save(files("A", ["D", "C", "B"]), path=os.path.join(client.current_folder, "A"))

        project = dedent("""
            editables:
                HelloD/0.1@lasote/stable:
                    path: D
                HelloB/0.1@lasote/stable:
                    path: B
                HelloC/0.1@lasote/stable:
                    path: C
                HelloA/0.1@lasote/stable:
                    path: A
            workspace_generator: cmake
            layout: layout
            root: HelloA/0.1@lasote/stable
            """)
        layout = dedent("""
            [build_folder]

            """)
        client.save({"conanws.yml": project,
                     "layout": layout})
        client.run("workspace install conanws.yml")
        self.assertIn("HelloA/0.1@lasote/stable from user folder - Editable", client.out)
        self.assertIn("HelloB/0.1@lasote/stable from user folder - Editable", client.out)
        self.assertIn("HelloC/0.1@lasote/stable from user folder - Editable", client.out)
        self.assertIn("HelloD/0.1@lasote/stable from user folder - Editable", client.out)

        a_cmake = load(os.path.join(client.current_folder, "A", "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS helloB helloC helloD ${CONAN_LIBS})", a_cmake)
        b_cmake = load(os.path.join(client.current_folder, "B", "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS helloC helloD ${CONAN_LIBS})", b_cmake)

    def missing_layout_cmake_test(self):
        # Specifying cmake generator without layout file raised exception
        # https://github.com/conan-io/conan/issues/4752
        client = TestClient()

        def files(name, depend=None):
            if isinstance(depend, list):
                deps = ", ".join(["'Hello%s/0.1@lasote/stable'" % d for d in depend])
            else:
                deps = ('"Hello%s/0.1@lasote/stable"' % depend) if depend else "None"
            return {"conanfile.py": conanfile_build.format(deps=deps, name=name)}

        client.save(files("D"), path=os.path.join(client.current_folder, "D"))
        client.save(files("C", "D"), path=os.path.join(client.current_folder, "C"))

        project = dedent("""
            editables:
                HelloD/0.1@lasote/stable:
                    path: D
                HelloC/0.1@lasote/stable:
                    path: C
            workspace_generator: cmake
            root: HelloC/0.1@lasote/stable
            """)

        client.save({"conanws.yml": project})
        client.run("workspace install conanws.yml", assert_error=True)
        self.assertIn("No layout defined for editable 'HelloD/0.1@lasote/stable' and cannot"
                      " find the default one neither", client.out)

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
        a = files("A", "B")
        a["src/CMakeLists.txt"] += ("add_executable(app main.cpp)\n"
                                    "target_link_libraries(app helloA)\n")
        a["src/main.cpp"] = main_cpp
        client.save(a, path=os.path.join(client.current_folder, "A"))

        project = dedent("""
            editables:
                HelloB/0.1@lasote/stable:
                    path: B
                HelloC/0.1@lasote/stable:
                    path: C
                HelloA/0.1@lasote/stable:
                    path: A
            layout: layout
            workspace_generator: cmake
            root: HelloA/0.1@lasote/stable
            """)
        layout = dedent("""
            [build_folder]
            build
            [source_folder]
            src
            [includedirs]
            src

            [libdirs]
            build/{{settings.build_type}}
            """)
        metacmake = dedent("""
            cmake_minimum_required(VERSION 3.3)
            project(MyProject CXX)
            include(${CMAKE_BINARY_DIR}/conanworkspace.cmake)
            conan_workspace_subdirectories()
            """)
        client.save({"conanws.yml": project,
                     "layout": layout,
                     "CMakeLists.txt": metacmake})

        build = os.path.join(client.current_folder, "build")

        with client.chdir("build"):
            client.run("workspace install ../conanws.yml")
            client.run("workspace install ../conanws.yml -s build_type=Debug")

        client.init_dynamic_vars()
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

        self.assertNotIn("Debug", client.out)

        client.runner('cmake .. -G "%s" -DCMAKE_BUILD_TYPE=Debug' % generator, cwd=build)
        # CMake configure will find the Release libraries, as we are in cmake-multi mode
        # Need to reset the output after that
        client.init_dynamic_vars()  # Reset output
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

        self.assertNotIn("Release", client.out)

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
            editables:
                HelloB/0.1@lasote/stable:
                    path: B
                HelloC/0.1@lasote/stable:
                    path: C
                HelloA/0.1@lasote/stable:
                    path: A
            workspace_generator: cmake
            layout: layout
            root: HelloA/0.1@lasote/stable
            """)
        layout = dedent("""
            [build_folder]
            build
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

    def use_build_requires_editable_test(self):
        client = TestClient()
        toolconanfile = """from conans import ConanFile
class Tool(ConanFile):
    def package_info(self):
        self.cpp_info.libs = ["MyToolLib"]
"""

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

        client.save({"conanfile.py": toolconanfile},
                    path=os.path.join(client.current_folder, "Tool"))
        client.save(files("A"), path=os.path.join(client.current_folder, "A"))

        project = dedent("""
            editables:
                HelloA/0.1@lasote/stable:
                    path: A
                Tool/0.1@user/testing:
                    path: Tool
            workspace_generator: cmake
            layout: layout
            root: HelloA/0.1@lasote/stable
            """)
        layout = dedent("""
            [build_folder]
            build
            """)
        client.save({"conanws.yml": project,
                     "layout": layout})

        client.run("workspace install conanws.yml")
        self.assertIn("HelloA/0.1@lasote/stable: Applying build-requirement: Tool/0.1@user/testing",
                      client.out)

        conanbuildinfo = load(os.path.join(client.current_folder, "A", "build",
                                           "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS_TOOL MyToolLib)", conanbuildinfo)

    def per_package_layout_test(self):
        client = TestClient()

        def files(name, depend=None):
            deps = ('"Hello%s/0.1@lasote/stable"' % depend) if depend else "None"
            return {"conanfile.py": conanfile_build.format(deps=deps, name=name)}

        client.save(files("C"), path=os.path.join(client.current_folder, "C"))
        client.save(files("B", "C"), path=os.path.join(client.current_folder, "B"))
        client.save(files("A", "B"), path=os.path.join(client.current_folder, "A"))

        project = dedent("""
            editables:
                HelloB/0.1@lasote/stable:
                    path: B
                    layout: B/layoutB
                HelloC/0.1@lasote/stable:
                    path: C
                    layout: C/layoutC
                HelloA/0.1@lasote/stable:
                    path: A
                    layout: A/layoutA
            workspace_generator: cmake
            root: HelloA/0.1@lasote/stable
            """)
        layout = dedent("""
            [build_folder]
            build

            [includedirs]
            myinclude{}
            """)
        client.save({"conanws.yml": project,
                     "A/layoutA": layout.format("A"),
                     "B/layoutB": layout.format("B"),
                     "C/layoutC": layout.format("C")})
        client.run("workspace install conanws.yml")
        self.assertIn("HelloA/0.1@lasote/stable from user folder - Editable", client.out)
        self.assertIn("HelloB/0.1@lasote/stable from user folder - Editable", client.out)
        self.assertIn("HelloC/0.1@lasote/stable from user folder - Editable", client.out)

        cmake = load(os.path.join(client.current_folder, "A", "build", "conanbuildinfo.cmake"))
        self.assertIn("myincludeC", cmake)
        self.assertIn("myincludeB", cmake)

    def test_default_filename(self):
        client = TestClient()
        path_to_editable = os.path.join(client.current_folder, "A")

        project = dedent("""
            editables:
                HelloA/0.1@lasote/stable:
                    path: {path_to_editable}
            layout: layout
            workspace_generator: cmake
            root: HelloA/0.1@lasote/stable
            """.format(path_to_editable=path_to_editable))

        conanfile = dedent("""
            from conans import ConanFile

            class Lib(ConanFile):
                pass
            """)

        layout = dedent("""
            [build_folder]
            [source_folder]
            """)

        client.save({"conanfile.py": conanfile}, path=path_to_editable)
        ws_folder = temp_folder()
        client.save({os.path.join(ws_folder, Workspace.default_filename): project,
                     os.path.join(ws_folder, "layout"): layout})

        # For a non existing folder, it will try to load the default filename (it fails)
        non_existing = temp_folder()
        client.run('workspace install "{}"'.format(non_existing), assert_error=True)
        trial_path = os.path.join(non_existing, Workspace.default_filename)
        self.assertIn("ERROR: Couldn't load workspace file in {}".format(trial_path), client.out)

        # For an existing file, it will try to use it (will fail because of the format)
        invalid_file = os.path.join(ws_folder, "layout")
        client.run('workspace install "{}"'.format(invalid_file), assert_error=True)
        self.assertIn("ERROR: There was an error parsing", client.out)

        # For an existing folder, without the default file (it will fail looking for it)
        no_default_file = os.path.join(client.current_folder)
        client.run('workspace install "{}"'.format(no_default_file), assert_error=True)
        trial_path = os.path.join(no_default_file, Workspace.default_filename)
        self.assertIn("ERROR: Couldn't load workspace file in {}".format(trial_path), client.out)

    def test_install_folder(self):
        project = dedent("""
            editables:
                HelloA/0.1@lasote/stable:
                    path: A
            layout: layout
            workspace_generator: cmake
            root: HelloA/0.1@lasote/stable
            """)

        conanfile = dedent("""
            from conans import ConanFile

            class Lib(ConanFile):
                pass
            """)

        layout = dedent("""
            [build_folder]
            [source_folder]
            """)

        client = TestClient()
        client.save({"conanfile.py": conanfile},
                    path=os.path.join(client.current_folder, "A"))

        client.save({"conanws.yml": project,
                     "layout": layout})
        client.run("workspace install conanws.yml --install-folder=ws_install")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "ws_install",
                                                    "conanworkspace.cmake")))

    def missing_subarguments_test(self):
        client = TestClient()
        client.run("workspace", assert_error=True)
        self.assertIn("ERROR: Exiting with code: 2", client.out)

