from conans.errors import ConanException
import re


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
        cmake = CMake(self)
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

conanfile_bare = """from conans import ConanFile

class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    settings = "os", "compiler", "build_type", "arch"
    description = "Package for {package_name}"
    url = "None"
    license = "None"

    def package_info(self):
        self.cpp_info.libs = self.collect_libs()
"""

conanfile_sources = """from conans import ConanFile, CMake


class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    license = "<Put the package license here>"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "Description of {package_name}"
    settings = "os", "compiler", "build_type", "arch"
    options = {{"shared": [True, False]}}
    default_options = "shared=False"
    generators = "cmake"
    exports_sources = "src/*"

    def build(self):
        cmake = CMake(self)
        self.run('cmake %s/src %s' % (self.source_folder, cmake.command_line))
        self.run("cmake --build . %s" % cmake.build_config)

    def package(self):
        self.copy("*.h", dst="include", src="src")
        self.copy("*.lib", dst="lib", keep_path=False)
        self.copy("*.dll", dst="bin", keep_path=False)
        self.copy("*.dylib*", dst="lib", keep_path=False)
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
        cmake = CMake(self)
        # Current dir is "test_package/build/<build_id>" and CMakeLists.txt is in "test_package"
        cmake.configure(source_dir=self.conanfile_directory, build_dir="./")
        cmake.build()

    def imports(self):
        self.copy("*.dll", dst="bin", src="bin")
        self.copy("*.dylib*", dst="bin", src="lib")

    def test(self):
        os.chdir("bin")
        self.run(".%sexample" % os.sep)
"""

test_cmake = """project(PackageTest CXX)
cmake_minimum_required(VERSION 2.8.12)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()

add_executable(example example.cpp)
target_link_libraries(example ${CONAN_LIBS})

# CTest is a testing tool that can be used to test your project.
# enable_testing()
# add_test(NAME example
#          WORKING_DIRECTORY ${CMAKE_BINARY_DIR}/bin
#          COMMAND example)
"""

test_main = """#include <iostream>
#include "hello.h"

int main() {
    hello();
}
"""

hello_h = """#pragma once

#ifdef WIN32
  #define HELLO_EXPORT __declspec(dllexport)
#else
  #define HELLO_EXPORT
#endif

HELLO_EXPORT void hello();
"""

hello_cpp = """#include <iostream>
#include "hello.h"

void hello(){
    #ifdef NDEBUG
    std::cout << "Hello World Release!" <<std::endl;
    #else
    std::cout << "Hello World Debug!" <<std::endl;
    #endif
}
"""

cmake = """project(MyHello CXX)
cmake_minimum_required(VERSION 2.8)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/bin)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_CURRENT_BINARY_DIR}/bin)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_CURRENT_BINARY_DIR}/bin)

set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})

add_library(hello hello.cpp)
"""


def get_files(ref, header=False, pure_c=False, test=False, exports_sources=False, bare=False):
    try:
        tokens = ref.split("@")
        name, version = tokens[0].split("/")
        if len(tokens) == 2:
            user, channel = tokens[1].split("/")
        else:
            user, channel = "user", "channel"

        pattern = re.compile('[\W_]+')
        package_name = pattern.sub('', name).capitalize()
    except:
        raise ConanException("Bad parameter, please use full package name,"
                             "e.g: MyLib/1.2.3@user/testing")

    if header and exports_sources:
        raise ConanException("--header and --sources are incompatible options")
    if pure_c and (header or exports_sources):
        raise ConanException("--pure_c is incompatible with --header and --sources")
    if bare and (header or exports_sources):
        raise ConanException("--bare is incompatible with --header and --sources")

    if header:
        files = {"conanfile.py": conanfile_header.format(name=name, version=version,
                                                         package_name=package_name)}
    elif exports_sources:
        files = {"conanfile.py": conanfile_sources.format(name=name, version=version,
                                                          package_name=package_name),
                 "src/hello.cpp": hello_cpp,
                 "src/hello.h": hello_h,
                 "src/CMakeLists.txt": cmake}
    elif bare:
        files = {"conanfile.py": conanfile_bare.format(name=name, version=version,
                                                       package_name=package_name)}
    else:
        files = {"conanfile.py": conanfile.format(name=name, version=version,
                                                  package_name=package_name)}
        if pure_c:
            config = "\n    def configure(self):\n        del self.settings.compiler.libcxx"
            files["conanfile.py"] = files["conanfile.py"] + config

    if test:
        files["test_package/conanfile.py"] = test_conanfile.format(name=name, version=version,
                                                                   user=user, channel=channel,
                                                                   package_name=package_name)
        files["test_package/CMakeLists.txt"] = test_cmake
        files["test_package/example.cpp"] = test_main

    return files
