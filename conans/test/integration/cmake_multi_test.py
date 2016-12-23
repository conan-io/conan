import unittest
from conans.test.tools import TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from nose.plugins.attrib import attr
import io
from conans.test.utils.runner import TestRunner


@attr("slow")
class CMakeMultiTest(unittest.TestCase):

    def diamond_cmake_test(self):
        client = TestClient()
        files = cpp_hello_conan_files("Hello0", "0.1")
        orig = "lang = '-DCONAN_LANGUAGE=%s' % self.options.language"
        replace = "lang = '-DCONAN_LANGUAGE=%s' % (0 if self.settings.build_type=='Debug' else 1)"
        files["conanfile.py"] = files["conanfile.py"].replace(orig, replace).replace('"arch"',
                                                                                     '"arch", "build_type"')
        client.save(files)
        client.run("export lasote/testing")
        files = cpp_hello_conan_files("Hello1", "0.1", deps=["Hello0/0.1@lasote/testing"])
        files["conanfile.py"] = files["conanfile.py"].replace(orig, replace).replace('"arch"',
                                                                                     '"arch", "build_type"')
        client.save(files, clean_first=True)
        client.run("export lasote/testing")

        conanfile = """[requires]
Hello1/0.1@lasote/testing
[generators]
cmake_multi
"""
        cmake = """
project(MyHello)
cmake_minimum_required(VERSION 2.8.12)

include(${CMAKE_BINARY_DIR}/conanbuildinfo_multi.cmake)
conan_basic_setup()

add_executable(say_hello main.cpp)
target_link_libraries(say_hello debug ${CONAN_LIBS_DEBUG} optimized ${CONAN_LIBS_RELEASE})
"""
        main = """
#include "helloHello1.h"

int main(){{
    helloHello1();
    return 0;
}}
"""

        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake,
                     "main.cpp": main}, clean_first=True)
        client.run('install -s build_type=Debug -s compiler="Visual Studio" -s compiler.runtime=MDd --build=missing')
        print client.user_io.out
        client.run("install -s build_type=Release --build=missing")
        print client.user_io.out
        output = io.StringIO()
        runner = TestRunner(output)
        runner('cmake . -G "Visual Studio 14 Win64"', cwd=client.current_folder)
        runner('cmake --build . --config Debug', cwd=client.current_folder)
        runner("bin\say_hello", cwd=client.current_folder)
        print output.getvalue()
        runner('cmake --build . --config Release', cwd=client.current_folder)
        runner("bin\say_hello", cwd=client.current_folder)
        print output.getvalue()
    