import platform

from conans.paths import BUILD_INFO_CMAKE, CONANFILE

conanfile_build_cmake = """    def build(self):
        defs = {
            "BUILD_SHARED_LIBS": not self.options.static,
            "CONAN_LANGUAGE": self.options.language
        }
        cmake = CMake(self)
        cmake.configure(defs=defs)
        cmake.build()"""


conanfile_template = """
from conans import ConanFile, CMake
from conans.tools import replace_in_file
import platform

class {name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    options = {{"language": [0, 1],
                "static": [True, False]}}
    default_options = '''language={language}
                        static= {static}'''
    requires = ({requires})
    settings = {settings}
    generators = "cmake"
    exports = '*'

    def config(self):
        {libcxx_remove}
        for name, req in self.requires.iteritems():
            self.options[name].language = self.options.language

    def source(self):
        # Try-except necessary, not all tests have all files
        try:
            replace_in_file("CMakeLists.txt", "projct", "project")
        except:
            pass
        try:
            replace_in_file("main.cpp", "retunr", "return")
        except:
            pass

{build}

    def package(self):
        self.copy(pattern="*.h", dst="include", keep_path=False)
        self.copy(pattern="*.lib", dst="lib", keep_path=False, excludes="*say*")
        self.copy(pattern="*lib*.a", dst="lib", keep_path=False)
        self.copy(pattern="*.dll", dst="bin", keep_path=False)
        self.copy(pattern="*.dylib", dst="lib", keep_path=False)
        self.copy(pattern="*.so", dst="lib", keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["hello{name}"]
{additional_info}
    def imports(self):
        self.copy(pattern="*.dylib", dst=".", src="lib")
        self.copy(pattern="*.dll", dst=".", src="bin")
        self.copy(pattern="*", dst="bin", src="bin")
"""

cmake_file = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)

include(${{CMAKE_BINARY_DIR}}/%s)

add_definitions(-DCONAN_LANGUAGE=${{CONAN_LANGUAGE}})
message("HELLO LANGUAGE " ${{CONAN_LANGUAGE}})
conan_basic_setup()

add_library(hello{name} hello{ext})
target_link_libraries(hello{name} ${{CONAN_LIBS}})
set_target_properties(hello{name}  PROPERTIES POSITION_INDEPENDENT_CODE ON)
if({with_exe})
    add_executable(say_hello main{ext})
    target_link_libraries(say_hello hello{name})
endif()


""" % BUILD_INFO_CMAKE

cmake_targets_file = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)

include(${{CMAKE_BINARY_DIR}}/%s)

add_definitions(-DCONAN_LANGUAGE=${{CONAN_LANGUAGE}})
message("HELLO LANGUAGE " ${{CONAN_LANGUAGE}})
conan_basic_setup(TARGETS)

add_library(hello{name} hello{ext})
target_link_libraries(hello{name} PUBLIC {targets})
set_target_properties(hello{name}  PROPERTIES POSITION_INDEPENDENT_CODE ON)
if({with_exe})
    add_executable(say_hello main{ext})
    target_link_libraries(say_hello hello{name})
endif()

""" % BUILD_INFO_CMAKE

body = r"""#include "hello{name}.h"

#include <iostream>
using namespace std;

{includes}

void hello{name}(){{
#if CONAN_LANGUAGE == 0
    cout<<"Hello {msg}\n";
#elif CONAN_LANGUAGE == 1
    cout<<"Hola {msg}\n";
#endif
    {other_calls}
}}
"""

body_c = r"""#include "hello{name}.h"

#include <stdio.h>

{includes}

void hello{name}(){{
#if CONAN_LANGUAGE == 0
    printf("Hello {msg}\n");
#elif CONAN_LANGUAGE == 1
    printf("Hola {msg}\n");
#endif
    {other_calls}
}}
"""
header = """
#pragma once
{includes}

#ifdef _WIN32
  #define HELLO_EXPORT __declspec(dllexport)
#else
  #define HELLO_EXPORT
#endif
HELLO_EXPORT void hello{name}();
"""

main = """
#include "hello{name}.h"

int main(){{
    hello{name}();
    return 0;
}}
"""

executable = """
"""


def cpp_hello_source_files(name="Hello", deps=None, private_includes=False, msg=None,
                           need_patch=False, pure_c=False, cmake_targets=False,
                           with_exe=False):
    """
    param number: integer, defining name of the conans Hello0, Hello1, HelloX
    param deps: [] list of integers, defining which dependencies this conans
                depends on
    param private_includes: includes will exist only in cpp, then hidden from
                            downstream consumers
    param msg: the message to append to Hello/Hola, will be equal the number
               by default
    param need_patch: It will generated wrong CMakeLists and main.cpp files,
                      so they will need to be fixed/patched in the source() method.
                      Such method just have to replace_in_file in those two files to have a
                      correct "source" directory. This was introduced to be sure that the
                      source and build methods are executed using their respective folders
                      while packaging.
    e.g. (3, [4, 7]) means that a Hello3 conans will be created, with message
         "Hello 3", that depends both in Hello4 and Hello7.
         The output of such a conans exe could be like: Hello 3, Hello 4, Hello7
    """
    assert deps is None or isinstance(deps, list)
    deps = deps or []
    if msg is None:
        msg = name
    ret = {}
    ext = ".c" if pure_c else ".cpp"
    ret["main%s" % ext] = main.format(name=name)
    includes = "\n".join(['#include "hello%s.h"' % d for d in deps])
    ret["hello%s.h" % name] = header.format(name=name,
                                            includes=(includes if not private_includes else ""))

    other_calls = "\n".join(["hello%s();" % d for d in deps])
    body_content = body if not pure_c else body_c
    ret["hello%s" % ext] = body_content.format(name=name,
                                               includes=includes,
                                               other_calls=other_calls,
                                               msg=msg)

    # Naive approximation, NO DEPS
    if cmake_targets:
        ret["CMakeLists.txt"] = cmake_targets_file.format(name=name, ext=ext,
                                                          targets=" ".join("CONAN_PKG::%s"
                                                                           % d for d in deps),
                                                          with_exe=str(with_exe))
    else:
        ret["CMakeLists.txt"] = cmake_file.format(name=name, ext=ext, with_exe=str(with_exe))
    if pure_c:
        ret["CMakeLists.txt"] = ret["CMakeLists.txt"].replace("project(MyHello CXX)",
                                                              "project(MyHello C)")
    if need_patch:
        ret["CMakeLists.txt"] = ret["CMakeLists.txt"].replace("project", "projct")
        ret["main%s" % ext] = ret["main%s" % ext].replace("return", "retunr")
    ret["executable"] = executable

    return ret


def cpp_hello_conan_files(name="Hello", version="0.1", deps=None, language=0, static=True,
                          private_includes=False, msg=None, need_patch=False,
                          pure_c=False, config=True, build=True,
                          cmake_targets=False, no_copy_source=False,
                          use_additional_infos=0, settings=None, with_exe=True):
    """Generate hello_files, as described above, plus the necessary
    CONANFILE to manage it
    param number: integer, defining name of the conans Hello0, Hello1, HelloX
    param version: string with the version of the current conans "0.1" by default
    param deps: [] list of string of the form "0/0.1@user/channel"
    param language: 0 = English, 1 = Spanish

    e.g. (3, [4, 7]) means that a Hello3 conans will be created, with message
         "Hello 3", that depends both in Hello4 and Hello7.
         The output of such a conans exe could be like: Hello 3, Hello 4, Hello7"""
    assert deps is None or isinstance(deps, list)
    settings = (settings or '"os", "compiler", "arch"')

    code_deps = []
    requires = []
    for d in deps or []:
        if isinstance(d, str):
            requires.append('"%s"' % d)
            code_dep = d.split("/", 1)[0]
        elif isinstance(d, tuple):
            requires.append('(%s)' % (", ".join('"%s"' % e for e in d)))
            code_dep = d[0].split("/", 1)[0]
        else:
            raise Exception("Wrong input %s %s" % (d, type(d)))
        code_deps.append(code_dep)
    requires.append("")
    requires = ", ".join(requires)

    base_files = cpp_hello_source_files(name, code_deps, private_includes, msg=msg,
                                        need_patch=need_patch,
                                        pure_c=pure_c, cmake_targets=cmake_targets,
                                        with_exe=with_exe)
    libcxx_remove = "del self.settings.compiler.libcxx" if pure_c else ""
    build_env = conanfile_build_cmake

    info_tmp = """
        self.env_info.%s.append("2")
        self.user_info.%s = "UserValue" """

    res = ""
    for i in range(use_additional_infos):
        res += info_tmp % ("EnvVar%d" % i, "UserVar%d" % i)

    conanfile = conanfile_template.format(name=name,
                                          version=version,
                                          requires=requires,
                                          language=language,
                                          static=static,
                                          libcxx_remove=libcxx_remove,
                                          build=build_env,
                                          additional_info=res,
                                          settings=settings)

    if no_copy_source:
        conanfile = conanfile.replace("exports = '*'", """exports = '*'
    no_copy_source=True""")

    if pure_c:
        conanfile = conanfile.replace("hello.cpp", "hello.c").replace("main.cpp", "main.c")
        conanfile = conanfile.replace("c++", "cc" if platform.system() != "Windows" else "gcc")
    if not build:
        conanfile = conanfile.replace("build(", "build2(")
    if not config:
        conanfile = conanfile.replace("config(", "config2(")

    base_files[CONANFILE] = conanfile
    return base_files
