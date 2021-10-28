conanfile_sources_v2 = """from conans import ConanFile
from conan.tools.cmake import CMakeToolchain, CMake
from conan.tools.layout import cmake_layout


class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"

    # Optional metadata
    license = "<Put the package license here>"
    author = "<Put your name here> <And your email here>"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "<Description of {package_name} here>"
    topics = ("<Put some tag here>", "<here>", "<and here>")

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"
    options = {{"shared": [True, False], "fPIC": [True, False]}}
    default_options = {{"shared": False, "fPIC": True}}

    # Sources are located in the same place as this recipe, copy them to the recipe
    exports_sources = "CMakeLists.txt", "src/*"

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def layout(self):
        cmake_layout(self)

    def generate(self):
        tc = CMakeToolchain(self)
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()

    def package_info(self):
        self.cpp_info.libs = ["{name}"]
"""


test_conanfile_v2 = """import os

from conans import ConanFile, tools
from conan.tools.cmake import CMake
from conan.tools.layout import cmake_layout


class {package_name}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    # VirtualBuildEnv and VirtualRunEnv can be avoided if "tools.env.virtualenv:auto_use" is defined
    # (it will be defined in Conan 2.0)
    generators = "CMakeDeps", "CMakeToolchain", "VirtualBuildEnv", "VirtualRunEnv"
    apply_env = False

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def layout(self):
        cmake_layout(self)

    def test(self):
        if not tools.cross_building(self):
            cmd = os.path.join(self.cpp.build.bindirs[0], "example")
            self.run(cmd, env="conanrun")
"""


test_cmake_v2 = """cmake_minimum_required(VERSION 3.15)
project(PackageTest CXX)

find_package({name} CONFIG REQUIRED)

add_executable(example src/example.cpp)
target_link_libraries(example {name}::{name})
"""


cmake_v2 = """cmake_minimum_required(VERSION 3.15)
project({name} CXX)

add_library({name} src/{name}.cpp)

set_target_properties({name} PROPERTIES PUBLIC_HEADER "src/{name}.h")
install(TARGETS {name} DESTINATION "."
        PUBLIC_HEADER DESTINATION include
        RUNTIME DESTINATION bin
        ARCHIVE DESTINATION lib
        LIBRARY DESTINATION lib
        )
"""


source_h = """#pragma once

#ifdef WIN32
  #define {name}_EXPORT __declspec(dllexport)
#else
  #define {name}_EXPORT
#endif

{name}_EXPORT void {name}();
"""


source_cpp = r"""#include <iostream>
#include "{name}.h"

void {name}(){{
    #ifdef NDEBUG
    std::cout << "{name}/{version}: Hello World Release!\n";
    #else
    std::cout << "{name}/{version}: Hello World Debug!\n";
    #endif

    // ARCHITECTURES
    #ifdef _M_X64
    std::cout << "  {name}/{version}: _M_X64 defined\n";
    #endif

    #ifdef _M_IX86
    std::cout << "  {name}/{version}: _M_IX86 defined\n";
    #endif

    #if __i386__
    std::cout << "  {name}/{version}: __i386__ defined\n";
    #endif

    #if __x86_64__
    std::cout << "  {name}/{version}: __x86_64__ defined\n";
    #endif

    // Libstdc++
    #if defined _GLIBCXX_USE_CXX11_ABI
    std::cout << "  {name}/{version}: _GLIBCXX_USE_CXX11_ABI "<< _GLIBCXX_USE_CXX11_ABI << "\n";
    #endif

    // COMPILER VERSIONS
    #if _MSC_VER
    std::cout << "  {name}/{version}: _MSC_VER" << _MSC_VER<< "\n";
    #endif

    #if _MSVC_LANG
    std::cout << "  {name}/{version}: _MSVC_LANG" << _MSVC_LANG<< "\n";
    #endif

    #if __cplusplus
    std::cout << "  {name}/{version}: __cplusplus" << __cplusplus<< "\n";
    #endif

    #if __INTEL_COMPILER
    std::cout << "  {name}/{version}: __INTEL_COMPILER" << __INTEL_COMPILER<< "\n";
    #endif

    #if __GNUC__
    std::cout << "  {name}/{version}: __GNUC__" << __GNUC__<< "\n";
    #endif

    #if __GNUC_MINOR__
    std::cout << "  {name}/{version}: __GNUC_MINOR__" << __GNUC_MINOR__<< "\n";
    #endif

    #if __clang_major__
    std::cout << "  {name}/{version}: __clang_major__" << __clang_major__<< "\n";
    #endif

    #if __clang_minor__
    std::cout << "  {name}/{version}: __clang_minor__" << __clang_minor__<< "\n";
    #endif

    #if __apple_build_version__
    std::cout << "  {name}/{version}: __apple_build_version__" << __apple_build_version__<< "\n";
    #endif

    // SUBSYSTEMS

    #if __MSYS__
    std::cout << "  {name}/{version}: __MSYS__" << __MSYS__<< "\n";
    #endif

    #if __MINGW32__
    std::cout << "  {name}/{version}: __MINGW32__" << __MINGW32__<< "\n";
    #endif

    #if __MINGW64__
    std::cout << "  {name}/{version}: __MINGW64__" << __MINGW64__<< "\n";
    #endif

    #if __CYGWIN__
    std::cout << "  {name}/{version}: __CYGWIN__" << __CYGWIN__<< "\n";
    #endif
}}
"""


test_main = """#include "{name}.h"

int main() {{
    {name}();
}}
"""


def get_cmake_lib_files(name, version, package_name="Pkg"):
    files = {"conanfile.py": conanfile_sources_v2.format(name=name, version=version,
                                                         package_name=package_name),
             "src/{}.cpp".format(name): source_cpp.format(name=name, version=version),
             "src/{}.h".format(name): source_h.format(name=name, version=version),
             "CMakeLists.txt": cmake_v2.format(name=name, version=version),
             "test_package/conanfile.py": test_conanfile_v2.format(name=name,
                                                                   version=version,
                                                                   package_name=package_name),
             "test_package/src/example.cpp": test_main.format(name=name),
             "test_package/CMakeLists.txt": test_cmake_v2.format(name=name)}
    return files


conanfile_exe = """from conans import ConanFile
from conan.tools.cmake import CMakeToolchain, CMake
from conan.tools.layout import cmake_layout


class {package_name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"

    # Optional metadata
    license = "<Put the package license here>"
    author = "<Put your name here> <And your email here>"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "<Description of {package_name} here>"
    topics = ("<Put some tag here>", "<here>", "<and here>")

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"

    # Sources are located in the same place as this recipe, copy them to the recipe
    exports_sources = "CMakeLists.txt", "src/*"

    def layout(self):
        cmake_layout(self)

    def generate(self):
        tc = CMakeToolchain(self)
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()
"""

cmake_exe_v2 = """cmake_minimum_required(VERSION 3.15)
project({name} CXX)

add_executable({name} src/{name}.cpp src/main.cpp)

install(TARGETS {name} DESTINATION "."
        RUNTIME DESTINATION bin
        ARCHIVE DESTINATION lib
        LIBRARY DESTINATION lib
        )
"""

test_conanfile_exe_v2 = """import os
from conans import ConanFile, tools


class {package_name}TestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    # VirtualRunEnv can be avoided if "tools.env.virtualenv:auto_use" is defined
    # (it will be defined in Conan 2.0)
    generators = "VirtualRunEnv"
    apply_env = False

    def test(self):
        if not tools.cross_building(self):
            self.run("{name}", env="conanrun")
"""


def get_cmake_exe_files(name, version, package_name="Pkg"):
    files = {"conanfile.py": conanfile_exe.format(name=name, version=version,
                                                  package_name=package_name),
             "src/{}.cpp".format(name): source_cpp.format(name=name, version=version),
             "src/{}.h".format(name): source_h.format(name=name, version=version),
             "src/main.cpp": test_main.format(name=name),
             "CMakeLists.txt": cmake_exe_v2.format(name=name, version=version),
             "test_package/conanfile.py": test_conanfile_exe_v2.format(name=name,
                                                                       version=version,
                                                                       package_name=package_name)
             }
    return files
