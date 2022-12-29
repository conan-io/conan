import os
import platform
import textwrap
import unittest

import pytest


from conans.client.tools import remove_from_path, no_op
from conans.test.assets.multi_config import multi_config_files
from conans.test.utils.tools import TestClient

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


@pytest.mark.slow
@pytest.mark.tool_cmake
class CMakeMultiTest(unittest.TestCase):

    @pytest.mark.tool_mingw64
    def test_cmake_multi_find(self):
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
                     "Release/FindHello.cmake": 'message(STATUS "FIND HELLO RELEASE!")',
                     "RelWithDebInfo/FindHello.cmake": 'message(STATUS "FIND HELLO RELWITHDEBINFO!")',
                     "MinSizeRel/FindHello.cmake": 'message(STATUS "FIND HELLO MINSIZEREL!")'
                     })
        client.run("export . lasote/testing")
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
        client.run("install . -s build_type=RelWithDebInfo --build=missing ")
        client.run("install . -s build_type=MinSizeRel --build=missing ")

        # in Linux it can remove /usr/bin from the path invalidating "cmake" and everything
        with remove_from_path("sh") if platform.system() == "Windows" else no_op():
            generator = "MinGW Makefiles" if platform.system() == "Windows" else "Unix Makefiles"
            client.run_command('cmake . -G "%s" -DCMAKE_BUILD_TYPE=Debug' % generator)
            self.assertIn("FIND HELLO DEBUG!", client.out)
            self.assertNotIn("FIND HELLO RELEASE!", client.out)

            client.run_command('cmake . -G "%s" -DCMAKE_BUILD_TYPE=Release' % generator)
            self.assertIn("FIND HELLO RELEASE!", client.out)
            self.assertNotIn("FIND HELLO DEBUG!", client.out)

            client.run_command('cmake . -G "%s" -DCMAKE_BUILD_TYPE=RelWithDebInfo' % generator)
            self.assertIn("FIND HELLO RELWITHDEBINFO!", client.out)

            client.run_command('cmake . -G "%s" -DCMAKE_BUILD_TYPE=MinSizeRel' % generator)
            self.assertIn("FIND HELLO MINSIZEREL!", client.out)

    @pytest.mark.skipif(platform.system() not in ["Windows", "Darwin"], reason="Exclude Linux")
    @pytest.mark.tool_cmake(version="3.19")
    def test_cmake_multi(self):
        client = TestClient()

        client.save(multi_config_files("Hello0", test=False), clean_first=True)
        client.run("export . lasote/testing")
        client.run("install Hello0/0.1@lasote/testing --build=missing")
        client.save(package_files("Hello1", ["Hello0"]), clean_first=True)
        client.run("export . lasote/testing")

        if platform.system() == "Windows":
            generator = "Visual Studio 14 Win64"
            debug_install = '-s compiler="Visual Studio" -s compiler.version=14 -s compiler.runtime=MDd'
            release_install = '-s compiler="Visual Studio" -s compiler.version=14 -s compiler.runtime=MD'
        elif platform.system() == "Darwin":
            generator = "Xcode"
            debug_install = ''
            release_install = ''

        # better in one test instead of two, because install time is amortized
        for cmake_file in (cmake_targets, cmake):
            client.save({"conanfile.txt": conanfile,
                         "CMakeLists.txt": cmake_file,
                         "main.cpp": main}, clean_first=True)
            client.run('install . -s build_type=Debug %s --build=missing' % debug_install)
            client.run('install . -s build_type=Release %s --build=missing' % release_install)
            client.run('install . -s build_type=RelWithDebInfo %s --build=missing' % release_install)
            client.run('install . -s build_type=MinSizeRel %s --build=missing' % release_install)

            client.run_command('cmake . -G "%s"' % generator)
            self.assertNotIn("WARN: Unknown compiler '", client.out)
            self.assertNotIn("', skipping the version check...", client.out)
            if cmake_file == cmake_targets:
                self.assertIn("Conan: Using cmake targets configuration", client.out)
            else:
                self.assertIn("Conan: Using cmake global configuration", client.out)

            # Debug
            client.run_command('cmake --build . --config Debug')
            hello_comand = os.sep.join([".", "Debug", "say_hello"])
            client.run_command(hello_comand)

            self.assertIn("Hello0:Debug Hello1:Debug", client.out)
            self.assertIn("Hello0Def:Debug Hello1Def:Debug", client.out)
            self.assertIn("Hello Debug Hello1", client.out)
            self.assertIn("Hello Debug Hello0", client.out)

            # Release
            client.run_command('cmake --build . --config Release')
            hello_comand = os.sep.join([".", "Release", "say_hello"])
            client.run_command(hello_comand)

            self.assertIn("Hello0:Release Hello1:Release", client.out)
            self.assertIn("Hello0Def:Release Hello1Def:Release", client.out)
            self.assertIn("Hello Release Hello1", client.out)
            self.assertIn("Hello Release Hello0", client.out)

            # RelWithDebInfo
            client.run_command('cmake --build . --config RelWithDebInfo')
            hello_comand = os.sep.join([".", "RelWithDebInfo", "say_hello"])
            client.run_command(hello_comand)

            self.assertIn("Hello0:RelWithDebInfo Hello1:RelWithDebInfo", client.out)
            self.assertIn("Hello0Def:RelWithDebInfo Hello1Def:RelWithDebInfo", client.out)
            self.assertIn("Hello Release Hello1", client.out)
            self.assertIn("Hello Release Hello0", client.out)

            # MinSizeRel
            client.run_command('cmake --build . --config MinSizeRel')
            hello_comand = os.sep.join([".", "MinSizeRel", "say_hello"])
            client.run_command(hello_comand)

            self.assertIn("Hello0:MinSizeRel Hello1:MinSizeRel", client.out)
            self.assertIn("Hello0Def:MinSizeRel Hello1Def:MinSizeRel", client.out)
            self.assertIn("Hello Release Hello1", client.out)
            self.assertIn("Hello Release Hello0", client.out)


@pytest.mark.tool_cmake
class CMakeMultiSystemLibsTest(unittest.TestCase):

    def test_system_libs(self):
        mylib = textwrap.dedent("""
            import os
            from conans import ConanFile

            class MyLib(ConanFile):

                def package_info(self):
                    self.cpp_info.debug.system_libs = ["sys1d"]
                    self.cpp_info.release.system_libs = ["sys1"]
                    self.cpp_info.libs = ["lib1"]
                    self.cpp_info.debug.libs = ["lib1debug"]
                    self.cpp_info.release.libs = ["lib1release"]
                """)
        consumer = textwrap.dedent("""
            import os
            from conans import ConanFile

            class Consumer(ConanFile):
                settings = "build_type"
                requires = "mylib/1.0@us/ch"
                generators = "cmake_multi"
                """)
        client = TestClient()
        client.save({"conanfile_mylib.py": mylib, "conanfile_consumer.py": consumer})
        client.run("create conanfile_mylib.py mylib/1.0@us/ch")
        client.run("install conanfile_consumer.py -s build_type=Release")
        content = client.load("conanbuildinfo_release.cmake")
        self.assertIn("set(CONAN_LIBS_RELEASE ${CONAN_LIBS_RELEASE} ${CONAN_SYSTEM_LIBS_RELEASE}"
                      " ${CONAN_FRAMEWORKS_FOUND_RELEASE})", content)
        self.assertIn("set(CONAN_PKG_LIBS_RELEASE lib1 lib1release ${CONAN_PKG_LIBS_RELEASE})",
                      content)
        self.assertIn("set(CONAN_LIBS_MYLIB_RELEASE ${CONAN_PKG_LIBS_MYLIB_RELEASE} "
                      "${CONAN_SYSTEM_LIBS_MYLIB_RELEASE} ${CONAN_FRAMEWORKS_FOUND_MYLIB_RELEASE})",
                      content)
        self.assertIn("set(CONAN_PKG_LIBS_MYLIB_RELEASE lib1 lib1release)", content)
        self.assertIn("set(CONAN_SYSTEM_LIBS_RELEASE sys1 ${CONAN_SYSTEM_LIBS_RELEASE})", content)
        self.assertIn("set(CONAN_SYSTEM_LIBS_MYLIB_RELEASE sys1)", content)

        client.run("install conanfile_consumer.py -s build_type=Debug")
        content = client.load("conanbuildinfo_debug.cmake")
        self.assertIn("set(CONAN_LIBS_DEBUG ${CONAN_LIBS_DEBUG} ${CONAN_SYSTEM_LIBS_DEBUG} "
                      "${CONAN_FRAMEWORKS_FOUND_DEBUG})", content)
        self.assertIn("set(CONAN_LIBS_MYLIB_DEBUG ${CONAN_PKG_LIBS_MYLIB_DEBUG} "
                      "${CONAN_SYSTEM_LIBS_MYLIB_DEBUG} ${CONAN_FRAMEWORKS_FOUND_MYLIB_DEBUG})",
                      content)
        self.assertIn("set(CONAN_PKG_LIBS_DEBUG lib1 lib1debug ${CONAN_PKG_LIBS_DEBUG})", content)
        self.assertIn("set(CONAN_PKG_LIBS_MYLIB_DEBUG lib1 lib1debug)", content)
        self.assertIn("set(CONAN_SYSTEM_LIBS_DEBUG sys1d ${CONAN_SYSTEM_LIBS_DEBUG})", content)
        self.assertIn("set(CONAN_SYSTEM_LIBS_MYLIB_DEBUG sys1d)", content)


@pytest.mark.tool_cmake
class CMakeMultiSyntaxTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 2.18)
            include(${CMAKE_BINARY_DIR}/conanbuildinfo_multi.cmake)
            conan_basic_setup(NO_OUTPUT_DIRS)
            """)
        self.client.save({"conanfile.txt": "[generators]\ncmake_multi\ncmake",
                          "CMakeLists.txt": cmakelists})
        self.client.run("install .")
        self.client.run("install . -s build_type=Debug")

    def test_conan_basic_setup_interface(self):
        """
        Check conan_basic_setup() interface is the same one for cmake and cmake_multi generators
        """
        conanbuildinfo = self.client.load("conanbuildinfo.cmake")
        conanbuildinfo_multi = self.client.load("conanbuildinfo_multi.cmake")
        expected = "set(options TARGETS NO_OUTPUT_DIRS SKIP_RPATH KEEP_RPATHS SKIP_STD SKIP_FPIC)"
        self.assertIn(expected, conanbuildinfo)
        self.assertIn(expected, conanbuildinfo_multi)

    def test_conan_basic_setup_output_dirs_warning(self):
        """
        Check warning when suing NO_OUTPUT_DIRS
        """
        self.client.run_command("cmake .")
        self.assertIn("CMake Warning at conanbuildinfo_multi.cmake", self.client.out)
        self.assertIn("Conan: NO_OUTPUT_DIRS has no effect with cmake_multi generator",
                      self.client.out)
