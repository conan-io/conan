import textwrap

import pytest

from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def client():
    t = TestClient()
    cpp = gen_function_cpp(name="mydep")
    h = gen_function_h(name="mydep")
    cmake = gen_cmakelists(libname="mydep", libsources=["mydep.cpp"])
    conanfile = textwrap.dedent("""
        import os
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class Conan(ConanFile):
            name = "mydep"
            version = "1.0"
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = "*.cpp", "*.h", "CMakeLists.txt"
            generators = "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                self.copy("*.h", dst="include")
                self.copy("*.lib", dst="lib", keep_path=False)
                self.copy("*.dll", dst="bin", keep_path=False)
                self.copy("*.dylib*", dst="lib", keep_path=False)
                self.copy("*.so", dst="lib", keep_path=False)
                self.copy("*.a", dst="lib", keep_path=False)

            def package_info(self):

                self.cpp_info.set_property("cmake_find_mode", "both")

                self.cpp_info.set_property("cmake_file_name", "MyDep")
                self.cpp_info.set_property("cmake_target_name", "MyDepTarget")

                self.cpp_info.set_property("cmake_module_file_name", "mi_dependencia")
                self.cpp_info.set_property("cmake_module_target_name", "mi_dependencia_target")
                self.cpp_info.set_property("cmake_module_target_namespace",
                                           "mi_dependencia_namespace")

                self.cpp_info.components["crispin"].libs = ["mydep"]
                self.cpp_info.components["crispin"].set_property("cmake_target_name",
                                                                 "MyCrispinTarget")
                self.cpp_info.components["crispin"].set_property("cmake_module_target_name",
                                                                 "mi_crispin_target")
        """)

    t.save({"conanfile.py": conanfile,
            "mydep.cpp": cpp,
            "mydep.h": h,
            "CMakeLists.txt": cmake})

    t.run("create .")
    return t


@pytest.mark.tool_cmake
def test_reuse_with_modules_and_config(client):
    cpp = gen_function_cpp(name="main")
    cmake = """
    set(CMAKE_CXX_COMPILER_WORKS 1)
    set(CMAKE_CXX_ABI_COMPILED 1)
    set(CMAKE_C_COMPILER_WORKS 1)
    set(CMAKE_C_ABI_COMPILED 1)

    cmake_minimum_required(VERSION 3.15)
    project(project CXX)

    add_executable(myapp main.cpp)
    find_package(MyDep) # This one will find the config
    target_link_libraries(myapp MyDepTarget::MyCrispinTarget)

    add_executable(myapp2 main.cpp)
    find_package(mi_dependencia) # This one will find the module
    target_link_libraries(myapp2 mi_dependencia_namespace::mi_crispin_target)

    """
    conanfile = GenConanfile().with_name("myapp")\
        .with_cmake_build().with_exports_sources("*.cpp", "*.txt").with_require("mydep/1.0")
    client.save({"conanfile.py": conanfile,
                 "main.cpp": cpp,
                 "CMakeLists.txt": cmake})

    client.run("install . -if=install")
    client.run("build . -if=install")
