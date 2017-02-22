import unittest
from conans.test.tools import TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from nose.plugins.attrib import attr
from six import StringIO
from conans.test.utils.runner import TestRunner
import platform
import os


conanfile = """[requires]
Hello1/0.1@lasote/testing
[generators]
cmake_multi
"""

cmake = """
project(MyHello)
cmake_minimum_required(VERSION 2.8.12)

# Some cross-building toolchains will define this
set(CMAKE_FIND_ROOT_PATH "/some/path")
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
include(${CMAKE_BINARY_DIR}/conanbuildinfo_multi.cmake)
conan_basic_setup()

add_executable(say_hello main.cpp)
foreach(_LIB ${CONAN_LIBS_RELEASE})
    target_link_libraries(say_hello optimized ${_LIB})
endforeach()
foreach(_LIB ${CONAN_LIBS_DEBUG})
    target_link_libraries(say_hello debug ${_LIB})
endforeach()
"""

cmake_targets = """
project(MyHello)
cmake_minimum_required(VERSION 2.8.12)

include(${CMAKE_BINARY_DIR}/conanbuildinfo_multi.cmake)
conan_basic_setup(TARGETS)

add_executable(say_hello main.cpp)
target_link_libraries(say_hello CONAN_PKG::Hello1)
"""

main = """
#include "helloHello1.h"
#include <iostream>

int main(){{
    std::cout<<"Hello0:"<<HELLO0BUILD<<" Hello1:"<<HELLO1BUILD<<std::endl;
    std::cout<<"Hello0Def:"<<HELLO0DEFINE<<" Hello1Def:"<<HELLO1DEFINE<<std::endl;
    helloHello1();
    return 0;
}}
"""


@attr("slow")
class CMakeMultiTest(unittest.TestCase):

    def cmake_multi_test(self):
        if platform.system() == "Windows":
            generator = "Visual Studio 14 Win64"
            debug_install = '-s compiler="Visual Studio" -s compiler.version=14 -s compiler.runtime=MDd'
            release_install = '-s compiler="Visual Studio" -s compiler.version=14 -s compiler.runtime=MD'
        elif platform.system() == "Darwin":
            generator = "Xcode"
            debug_install = ''
            release_install = ''
        else:
            return
        client = TestClient()

        def prepare_files(files, number):
            # Change language according to build_type, to check
            orig = '"CONAN_LANGUAGE": self.options.language'
            replace = '"CONAN_LANGUAGE": 0 if self.settings.build_type=="Debug" else 1'
            conanfile = files["conanfile.py"]
            # The test files, surprisingly, dont use build_type
            conanfile = conanfile.replace(orig, replace).replace('"arch"', '"arch", "build_type"')
            # Header of the package will contain a different DEFINE, to make sure that it includes
            # the correct one
            conanfile = conanfile.replace("def build(self):\n", """def build(self):
        with open("helloHello{0}.h", "a") as f:
            f.write('#define HELLO{0}BUILD "%s"' % self.settings.build_type)
""".format(number))
            conanfile = conanfile.replace("def package_info(self):\n", """def package_info(self):
        self.cpp_info.defines = ['HELLO{}DEFINE="%s"' % self.settings.build_type]
""".format(number))
            files["conanfile.py"] = conanfile
            client.save(files, clean_first=True)
            client.run("export lasote/testing")

        files = cpp_hello_conan_files("Hello0", "0.1")
        prepare_files(files, 0)
        files = cpp_hello_conan_files("Hello1", "0.1", deps=["Hello0/0.1@lasote/testing"])
        prepare_files(files, 1)

        # better in one test instead of two, because install time is amortized
        for cmake_file in (cmake, cmake_targets, ):
            client.save({"conanfile.txt": conanfile,
                         "CMakeLists.txt": cmake_file,
                         "main.cpp": main}, clean_first=True)
            client.run('install -s build_type=Debug %s --build=missing' % debug_install)
            client.run('install -s build_type=Release %s --build=missing' % release_install)
            output = StringIO()
            runner = TestRunner(output)
            runner('cmake . -G "%s"' % generator, cwd=client.current_folder)
            self.assertNotIn("WARN: Unknown compiler '", output.getvalue())
            self.assertNotIn("', skipping the version check...", output.getvalue())
            runner('cmake --build . --config Debug', cwd=client.current_folder)
            hello_comand = os.sep.join([".", "Debug", "say_hello"])
            runner(hello_comand, cwd=client.current_folder)
            outstr = output.getvalue()
            self.assertIn("Hello0:Debug Hello1:Debug", outstr)
            self.assertIn("Hello Hello1", outstr)
            self.assertIn("Hello Hello0", outstr)
            runner('cmake --build . --config Release', cwd=client.current_folder)
            hello_comand = os.sep.join([".", "Release", "say_hello"])
            runner(hello_comand, cwd=client.current_folder)
            outstr = output.getvalue()
            self.assertIn("Hello0:Release Hello1:Release", outstr)
            self.assertIn("Hola Hello1", outstr)
            self.assertIn("Hola Hello0", outstr)
            if cmake_file == cmake_targets:
                self.assertIn("Conan: Using cmake targets configuration", outstr)
            else:
                self.assertIn("Conan: Using cmake global configuration", outstr)
