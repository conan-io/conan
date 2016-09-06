conanfile = """from conans import ConanFile, CMake, tools
import os


class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    license = "<Put the package license here>"
    url = "<Package recipe repository url here, for issues about the package>"
    settings = "os", "compiler", "build_type", "arch"
    options = {{"shared": [True, False]}}
    default_options = "shared=False"
    generators = "cmake"

    def source(self):
       self.run("git clone https://github.com/memsharded/hello.git")
       self.run("cd hello && git checkout static_shared")
       # This small hack might be useful to guarantee proper /MT /MD linkage in MSVC
       # if the packaged project doesn't have variables to set it properly
       tools.replace_in_file("hello/CMakeLists.txt", "PROJECT(MyHello)", '''PROJECT(MyHello)
include(${{CMAKE_BINARY_DIR}}/conanbuildinfo.cmake)
conan_basic_setup()''')

    def build(self):
        cmake = CMake(self.settings)
        shared = "-DBUILD_SHARED_LIBS=ON" if self.options.shared else ""
        self.run('cmake hello %s %s' % (cmake.command_line, shared))
        self.run("cmake --build . %s" % cmake.build_config)

    def package(self):
        self.copy("*.h", dst="include", src="hello")
        self.copy("*hello.lib", dst="lib", keep_path=False)
        self.copy("*.dll", dst="bin", keep_path=False)
        self.copy("*.so", dst="lib", keep_path=False)
        self.copy("*.a", dst="lib", keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["hello"]
"""


conanfile_header = """from conans import ConanFile, tools
import os


class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    license = "<Put the package license here>"
    url = "<Package recipe repository url here, for issues about the package>"
    # No settings/options are necessary, this is header only

    def source(self):
        '''retrieval of the source code here. Remember you can also put the code in the folder and
        use exports instead of retrieving it with this source() method
        '''
        #self.run("git clone ...") or
        #tools.download("url", "file.zip")
        #tools.unzip("file.zip" )

    def package(self):
        self.copy("*.h", "include")
"""


test_conanfile = """from conans import ConanFile, CMake
import os


channel = os.getenv("CONAN_CHANNEL", "{channel}")
username = os.getenv("CONAN_USERNAME", "{user}")


class {package_name}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    requires = "{name}/{version}@%s/%s" % (username, channel)
    generators = "cmake"

    def build(self):
        cmake = CMake(self.settings)
        self.run('cmake "%s" %s' % (self.conanfile_directory, cmake.command_line))
        self.run("cmake --build . %s" % cmake.build_config)

    def imports(self):
        self.copy("*.dll", "bin", "bin")
        self.copy("*.dylib", "bin", "bin")

    def test(self):
        os.chdir("bin")
        self.run(".%sexample" % os.sep)
"""

test_cmake = """PROJECT(PackageTest)
cmake_minimum_required(VERSION 2.8.12)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()

ADD_EXECUTABLE(example example.cpp)
TARGET_LINK_LIBRARIES(example ${CONAN_LIBS})
"""

test_main = """#include <iostream>
#include "hello.h"

int main() {
    hello();
    std::cout<<"*** Running example, will fail by default, implement yours! ***\\n";
    return -1; // fail by default, remember to implement your test
}
"""
