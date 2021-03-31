conanfile_sources_v2 = """from conans import ConanFile
from conan.tools.cmake import CMakeToolchain, CMake


class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
    license = "<Put the package license here>"
    author = "<Put your name here> <And your email here>"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "<Description of {package_name} here>"
    topics = ("<Put some tag here>", "<here>", "<and here>")
    settings = "os", "compiler", "build_type", "arch"
    options = {{"shared": [True, False], "fPIC": [True, False]}}
    default_options = {{"shared": False, "fPIC": True}}
    exports_sources = "src/*"

{configure}
    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def generate(self):
        tc = CMakeToolchain(self)
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure(source_folder="src")
        cmake.build()

    def package(self):
        self.copy("*.h", dst="include", src="src")
        self.copy("*.lib", dst="lib", keep_path=False)
        self.copy("*.dll", dst="bin", keep_path=False)
        self.copy("*.dylib*", dst="lib", keep_path=False)
        self.copy("*.so", dst="lib", keep_path=False)
        self.copy("*.a", dst="lib", keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["{name}"]
"""


test_conanfile_v2 = """import os

from conans import ConanFile, tools
from conan.tools.cmake import CMake


class {package_name}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    generators = "CMakeDeps", "CMakeToolchain", "VirtualEnv"
    apply_env = False

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if not tools.cross_building(self):
            self.run(os.path.sep.join([".", "bin", "example"]), env="conanrunenv")
"""


test_cmake_v2 = """cmake_minimum_required(VERSION 3.15)
project(PackageTest CXX)

# TODO: Remove this when layouts are available
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${{CMAKE_CURRENT_BINARY_DIR}}/bin)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${{CMAKE_RUNTIME_OUTPUT_DIRECTORY}})
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO ${{CMAKE_RUNTIME_OUTPUT_DIRECTORY}})
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL ${{CMAKE_RUNTIME_OUTPUT_DIRECTORY}})
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${{CMAKE_RUNTIME_OUTPUT_DIRECTORY}})

find_package({name} CONFIG REQUIRED)

add_executable(example example.cpp)
target_link_libraries(example {name}::{name})
"""


cmake_v2 = """cmake_minimum_required(VERSION 3.15)
project({name} CXX)

add_library({name} {name}.cpp)
"""


source_h = """#pragma once

#ifdef WIN32
  #define {name}_EXPORT __declspec(dllexport)
#else
  #define {name}_EXPORT
#endif

{name}_EXPORT void {name}();
"""


source_cpp = """#include <iostream>
#include "{name}.h"

void {name}(){{
    #ifdef NDEBUG
    std::cout << "{name}/{version}: Hello World Release!" <<std::endl;
    #else
    std::cout << "{name}/{version}: Hello World Debug!" <<std::endl;
    #endif
}}
"""


test_main = """#include "{name}.h"

int main() {{
    {name}();
}}
"""


def get_files(name, version, user, channel, package_name):
    files = {"conanfile.py": conanfile_sources_v2.format(name=name, version=version,
                                                         package_name=package_name,
                                                         configure=""),
             "src/{}.cpp".format(name): source_cpp.format(name=name, version=version),
             "src/{}.h".format(name): source_h.format(name=name, version=version),
             "src/CMakeLists.txt": cmake_v2.format(name=name, version=version),
             "test_package/conanfile.py": test_conanfile_v2.format(name=name,
                                                                   version=version,
                                                                   user=user,
                                                                   channel=channel,
                                                                   package_name=package_name),
             "test_package/example.cpp": test_main.format(name=name),
             "test_package/CMakeLists.txt": test_cmake_v2.format(name=name)}
    return files
