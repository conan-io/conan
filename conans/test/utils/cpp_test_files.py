from conans.paths import CONANFILE, BUILD_INFO_CMAKE


conanfile_build_cmake = """    def build(self):
        static_flags = "-DBUILD_SHARED_LIBS=ON" if not self.options.static else ""
        lang = '-DCONAN_LANGUAGE=%s' % self.options.language
        cmake = CMake(self.settings)
        cmake_flags = cmake.command_line
        cmd = 'cmake "%s" %s %s %s' % (self.conanfile_directory, cmake_flags, lang, static_flags)
        #print "Executing command ", cmd
        self.run(cmd)
        self.run("cmake --build . %s" % cmake.build_config)"""

conanfile_build_env = """
    def build(self):
        import os
        from conans import ConfigureEnvironment

        environment = ConfigureEnvironment(self)
        env = environment.command_line_env
        flags = environment.compile_flags

        if self.settings.compiler == "Visual Studio":
            lang = '/DCONAN_LANGUAGE=%s' % self.options.language
            if self.options.static:
                self.run('{}  && cl /c /EHsc hello.cpp {}'.format(env, lang))
                self.run('{} && lib hello.obj -OUT:hello{}.lib'.format(env, self.name))
            else:
                self.run('{} && cl /EHsc /LD hello.cpp {} {} /link /IMPLIB:hello{}.lib '
                         '/link /OUT:hello{}.dll'.format(env, lang, flags, self.name, self.name))

            command = ('{} && cl /EHsc main.cpp hello{}.lib {}'.format(env, self.name, flags))
            self.run(command)
        elif self.settings.compiler == "gcc" or "clang" in str(self.settings.compiler):
            # libs = " ".join("-l%s" % lib for lib in self.deps_cpp_info.libs)
            lang = '-DCONAN_LANGUAGE=%s' % self.options.language
            if self.options.static:
                self.run("g++ -c hello.cpp {} {}".format(lang, flags))
                self.run("{} && ar rcs libhello{}.a hello.o".format(env, self.name))
            else:
                if self.settings.os == "Windows":
                    self.run("{} && g++ -o libhello{}.dll -shared -fPIC hello.cpp {} {} "
                             "-Wl,--out-implib,libhello{}.a".
                             format(env, self.name, lang, flags, self.name))
                else:
                    self.run("{} && g++ -o libhello{}.so -shared -fPIC hello.cpp {} {}".
                    format(env, self.name, flags, lang))
            self.run('{} && g++ -o main main.cpp -L. -lhello{} {}'.format(env, self.name, flags))

        try:
            os.makedirs("bin")
        except:
            pass

        try:
            if self.settings.os == "Windows":
                os.rename("main.exe", "bin/say_hello.exe")
            else:
                os.rename("main", "bin/say_hello")
                if not self.options.static:
                    os.rename("libhello.so", "bin/libhello.so")
        except:
            pass
"""

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
    settings = "os", "compiler", "arch"
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
        self.copy(pattern="*", dst="bin", src="bin")
"""

cmake_file = """
project(MyHello)
cmake_minimum_required(VERSION 2.8.12)

include(${{CMAKE_BINARY_DIR}}/%s)

add_definitions(-DCONAN_LANGUAGE=${{CONAN_LANGUAGE}})
message("HELLO LANGUAGE " ${{CONAN_LANGUAGE}})
conan_basic_setup()

add_library(hello{name} hello{ext})
target_link_libraries(hello{name} ${{CONAN_LIBS}})
set_target_properties(hello{name}  PROPERTIES POSITION_INDEPENDENT_CODE ON)
add_executable(say_hello main{ext})
target_link_libraries(say_hello hello{name})


""" % BUILD_INFO_CMAKE

cmake_targets_file = """
project(MyHello)
cmake_minimum_required(VERSION 2.8.12)

include(${{CMAKE_BINARY_DIR}}/%s)

add_definitions(-DCONAN_LANGUAGE=${{CONAN_LANGUAGE}})
message("HELLO LANGUAGE " ${{CONAN_LANGUAGE}})
conan_basic_setup(TARGETS)

add_library(hello{name} hello{ext})
target_link_libraries(hello{name} PUBLIC {targets})
set_target_properties(hello{name}  PROPERTIES POSITION_INDEPENDENT_CODE ON)
add_executable(say_hello main{ext})
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
{export}void hello{name}();
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
                           dll_export=False, need_patch=False, pure_c=False, cmake_targets=False):
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
    export = "__declspec(dllexport) " if dll_export else ""
    ret["hello%s.h" % name] = header.format(name=name,
                                            export=export,
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
                                                                           % d for d in deps))
    else:
        ret["CMakeLists.txt"] = cmake_file.format(name=name, ext=ext)
    if pure_c:
        ret["CMakeLists.txt"] = ret["CMakeLists.txt"].replace("project(MyHello)",
                                                              "project(MyHello C)")
    if need_patch:
        ret["CMakeLists.txt"] = ret["CMakeLists.txt"].replace("project", "projct")
        ret["main%s" % ext] = ret["main%s" % ext].replace("return", "retunr")
    ret["executable"] = executable

    return ret


def cpp_hello_conan_files(name="Hello", version="0.1", deps=None, language=0, static=True,
                          private_includes=False, msg=None, dll_export=False, need_patch=False,
                          pure_c=False, config=True, build=True, collect_libs=False,
                          use_cmake=True, cmake_targets=False):
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
                                        dll_export=dll_export, need_patch=need_patch,
                                        pure_c=pure_c, cmake_targets=cmake_targets)
    libcxx_remove = "del self.settings.compiler.libcxx" if pure_c else ""
    build_env = conanfile_build_cmake if use_cmake else conanfile_build_env
    conanfile = conanfile_template.format(name=name,
                                          version=version,
                                          requires=requires,
                                          language=language,
                                          static=static,
                                          libcxx_remove=libcxx_remove,
                                          build=build_env)
    if pure_c:
        conanfile = conanfile.replace("hello.cpp", "hello.c").replace("main.cpp", "main.c")
        conanfile = conanfile.replace("g++", "gcc")
    if not build:
        conanfile = conanfile.replace("build(", "build2(")
    if not config:
        conanfile = conanfile.replace("config(", "config2(")
    if collect_libs:
        conanfile = conanfile.replace('["hello%s"]' % name,
                                      "self.collect_libs()")
    base_files[CONANFILE] = conanfile
    return base_files
