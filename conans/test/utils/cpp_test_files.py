from conans.paths import CONANFILE, BUILD_INFO_CMAKE


conanfile_template = """
from conans import ConanFile, CMake
import platform

class {name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    options = {{"language": [0, 1],
                "static": [True, False]}}
    default_options = '''language={language}
                        static= {static}'''
    requires = ({requires})
    settings = "os", "compiler", "arch"
    generators = "cmake"
    exports = '*'

    def config(self):
        for name, req in self.requires.iteritems():
            self.options[name].language = self.options.language

    def build(self):
        static_flags = "-DBUILD_SHARED_LIBS=ON" if not self.options.static else ""
        lang = '-DCONAN_LANGUAGE=%s' % self.options.language
        cmake = CMake(self.settings)
        cmake_flags = cmake.command_line
        cmd = 'cmake "%s" %s %s %s' % (self.conanfile_directory, cmake_flags, lang, static_flags)
        #print "Executing command ", cmd
        self.run(cmd)
        self.run("cmake --build . %s" % cmake.build_config)

    def package(self):
        self.copy(pattern="*.h", dst="include", keep_path=False)
        self.copy(pattern="*.lib", dst="lib", keep_path=False)
        self.copy(pattern="*lib*.a", dst="lib", keep_path=False)
        self.copy(pattern="*.dll", dst="bin", keep_path=False)
        self.copy(pattern="*.dylib", dst="lib", keep_path=False)
        self.copy(pattern="*.so", dst="lib", keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["hello{name}"]

    def imports(self):
        self.copy(pattern="*.dylib", dst=".", src="lib")
        self.copy(pattern="*.dll", dst=".", src="bin")
"""

cmake_file = """
project(MyHello)
cmake_minimum_required(VERSION 2.8.12)

include(${{CMAKE_BINARY_DIR}}/%s)

add_definitions(-DCONAN_LANGUAGE=${{CONAN_LANGUAGE}})
message("HELLO LANGUAGE " ${{CONAN_LANGUAGE}})
conan_basic_setup()

add_library(hello{name} hello.cpp)
target_link_libraries(hello{name} ${{CONAN_LIBS}})
set_target_properties(hello{name}  PROPERTIES POSITION_INDEPENDENT_CODE ON)
add_executable(say_hello main.cpp)
target_link_libraries(say_hello hello{name})


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
header = """
#pragma once
{includes}
{export}void hello{name}();
"""

main = """
#include "hello{name}.h"

int main(){{
    hello{name}();
    return 0;
}}
"""


def cpp_hello_source_files(name="Hello", deps=None, private_includes=False,
                           msg=None, dll_export=False):
    """
    param number: integer, defining name of the conans Hello0, Hello1, HelloX
    param deps: [] list of integers, defining which dependencies this conans
                depends on
    param private_includes: includes will exist only in cpp, then hidden from
                            downstream consumers
    param msg: the message to append to Hello/Hola, will be equal the number
               by default
    param dll_export: Adds __declspec(dllexport) to the .h declaration
                      (to be exported to lib with a dll)
    e.g. (3, [4, 7]) means that a Hello3 conans will be created, with message
         "Hello 3", that depends both in Hello4 and Hello7.
         The output of such a conans exe could be like: Hello 3, Hello 4, Hello7
    """
    assert deps is None or isinstance(deps, list)
    deps = deps or []
    if msg is None:
        msg = name
    ret = {}
    ret["main.cpp"] = main.format(name=name)
    includes = "\n".join(['#include "hello%s.h"' % d for d in deps])
    export = "__declspec(dllexport) " if dll_export else ""
    ret["hello%s.h" % name] = header.format(name=name,
                                            export=export,
                                            includes=(includes if not private_includes else ""))

    other_calls = "\n".join(["hello%s();" % d for d in deps])
    ret["hello.cpp"] = body.format(name=name,
                                   includes=includes,
                                   other_calls=other_calls,
                                   msg=msg)

    # Naive approximation, NO DEPS
    ret["CMakeLists.txt"] = cmake_file.format(name=name)
    return ret


def cpp_hello_conan_files(name="Hello", version="0.1", deps=None, language=0, static=True,
                          private_includes=False, msg=None, dll_export=False):
    """Generate hello_files, as described above, plus the necessary
    CONANFILE to manage it
    param number: integer, defining name of the conans Hello0, Hello1, HelloX
    param version: string with the version of the current conans "0.1" by default
    param deps: [] list of string of the form "0/0.1@user/channel"
    param language: 0 = English, 1 = Spanish
    param dll_export: Adds __declspec(dllexport) to the .h declaration
                      (to be exported to lib with a dll)

    e.g. (3, [4, 7]) means that a Hello3 conans will be created, with message
         "Hello 3", that depends both in Hello4 and Hello7.
         The output of such a conans exe could be like: Hello 3, Hello 4, Hello7"""
    assert deps is None or isinstance(deps, list)

    code_deps = []
    requires = []
    for d in deps or []:
        if isinstance(d, basestring):
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
                                        dll_export=dll_export)
    conanfile = conanfile_template.format(name=name,
                                      version=version,
                                      requires=requires,
                                      language=language,
                                      static=static)
    base_files[CONANFILE] = conanfile
    return base_files
