import re
from conans.errors import ConanException
from conans.model.ref import ConanFileReference
from conans.client.cmd.new_ci import ci_get_files


conanfile = """from conans import ConanFile, CMake, tools


class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    license = "<Put the package license here>"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "<Description of {package_name} here>"
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
        cmake.configure(source_folder="hello")
        cmake.build()

        # Explicit way:
        # self.run('cmake %s/hello %s' % (self.source_folder, cmake.command_line))
        # self.run("cmake --build . %s" % cmake.build_config)

    def package(self):
        self.copy("*.h", dst="include", src="hello")
        self.copy("*hello.lib", dst="lib", keep_path=False)
        self.copy("*.dll", dst="bin", keep_path=False)
        self.copy("*.so", dst="lib", keep_path=False)
        self.copy("*.dylib", dst="lib", keep_path=False)
        self.copy("*.a", dst="lib", keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["hello"]
"""

conanfile_bare = """from conans import ConanFile
from conans import tools

class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    settings = "os", "compiler", "build_type", "arch"
    description = "<Description of {package_name} here>"
    url = "None"
    license = "None"

    def package(self):
        self.copy("*")

    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)
"""

conanfile_sources = """from conans import ConanFile, CMake


class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    license = "<Put the package license here>"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "<Description of {package_name} here>"
    settings = "os", "compiler", "build_type", "arch"
    options = {{"shared": [True, False]}}
    default_options = "shared=False"
    generators = "cmake"
    exports_sources = "src/*"

    def build(self):
        cmake = CMake(self)
        cmake.configure(source_folder="src")
        cmake.build()

        # Explicit way:
        # self.run('cmake %s/src %s' % (self.source_folder, cmake.command_line))
        # self.run("cmake --build . %s" % cmake.build_config)

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
    description = "<Description of {package_name} here>"
    no_copy_source = True
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


test_conanfile = """from conans import ConanFile, CMake, tools
import os

class {package_name}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        # Current dir is "test_package/build/<build_id>" and CMakeLists.txt is in "test_package"
        cmake.configure()
        cmake.build()

    def imports(self):
        self.copy("*.dll", dst="bin", src="bin")
        self.copy("*.dylib*", dst="bin", src="lib")
        self.copy('*.so*', dst='bin', src='lib')

    def test(self):
        if not tools.cross_building(self.settings):
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

add_library(hello hello.cpp)
"""

gitignore_template = """
*.pyc
test_package/build

"""


def cmd_new(ref, header=False, pure_c=False, test=False, exports_sources=False, bare=False,
            visual_versions=None, linux_gcc_versions=None, linux_clang_versions=None, osx_clang_versions=None,
            shared=None, upload_url=None, gitignore=None, gitlab_gcc_versions=None, gitlab_clang_versions=None):
    try:
        tokens = ref.split("@")
        name, version = tokens[0].split("/")
        if len(tokens) == 2:
            user, channel = tokens[1].split("/")
        else:
            user, channel = "user", "channel"

        pattern = re.compile('[\W_]+')
        package_name = pattern.sub('', name).capitalize()
    except ValueError:
        raise ConanException("Bad parameter, please use full package name,"
                             "e.g: MyLib/1.2.3@user/testing")

    # Validate it is a valid reference
    ConanFileReference(name, version, user, channel)

    if header and exports_sources:
        raise ConanException("'header' and 'sources' are incompatible options")
    if pure_c and (header or exports_sources):
        raise ConanException("'pure_c' is incompatible with 'header' and 'sources'")
    if bare and (header or exports_sources):
        raise ConanException("'bare' is incompatible with 'header' and 'sources'")

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

    if gitignore:
        files[".gitignore"] = gitignore_template

    files.update(ci_get_files(name, version, user, channel, visual_versions,
                              linux_gcc_versions, linux_clang_versions,
                              osx_clang_versions, shared, upload_url,
                              gitlab_gcc_versions, gitlab_clang_versions))
    return files
