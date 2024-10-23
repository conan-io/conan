import os
import shutil
import textwrap

import pytest

from conan.test.assets.sources import gen_function_h, gen_function_cpp
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient


@pytest.fixture(scope="session")
def _matrix_client():
    """
    engine/1.0->matrix/1.0
    """
    c = TestClient()
    c.run("new cmake_lib -d name=matrix -d version=1.0")
    c.run("create . -tf=")
    return c


@pytest.fixture()
def matrix_client(_matrix_client):
    c = TestClient()
    c.cache_folder = os.path.join(temp_folder(), ".conan2")
    shutil.copytree(_matrix_client.cache_folder, c.cache_folder)
    return c


@pytest.fixture(scope="session")
def _transitive_libraries(_matrix_client):
    """
    engine/1.0->matrix/1.0
    """
    c = TestClient()
    c.cache_folder = os.path.join(temp_folder(), ".conan2")
    shutil.copytree(_matrix_client.cache_folder, c.cache_folder)
    c.save({}, clean_first=True)
    c.run("new cmake_lib -d name=engine -d version=1.0 -d requires=matrix/1.0")
    # create both static and shared
    c.run("create . -tf=")
    c.run("create . -o engine/*:shared=True -tf=")
    return c


@pytest.fixture()
def transitive_libraries(_transitive_libraries):
    c = TestClient()
    c.cache_folder = os.path.join(temp_folder(), ".conan2")
    shutil.copytree(_transitive_libraries.cache_folder, c.cache_folder)
    return c


@pytest.fixture(scope="session")
def _matrix_client_components():
    """
    2 components, different than the package name
    """
    c = TestClient()
    headers_h = textwrap.dedent("""
        #include <iostream>
        #ifndef MY_MATRIX_HEADERS_DEFINE
        #error "Fatal error MY_MATRIX_HEADERS_DEFINE not defined"
        #endif
        void headers(){ std::cout << "Matrix headers: Release!" << std::endl;
            #if __cplusplus
            std::cout << "  Matrix headers __cplusplus: __cplusplus" << __cplusplus << std::endl;
            #endif
        }
        """)
    vector_h = gen_function_h(name="vector")
    vector_cpp = gen_function_cpp(name="vector", includes=["vector"])
    module_h = gen_function_h(name="module")
    module_cpp = gen_function_cpp(name="module", includes=["module", "vector"], calls=["vector"])

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class Matrix(ConanFile):
            name = "matrix"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"
            exports_sources = "src/*", "CMakeLists.txt"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.default_components = ["vector", "module"]

                self.cpp_info.components["headers"].includedirs = ["include/headers"]
                self.cpp_info.components["headers"].set_property("cmake_target_name", "MatrixHeaders")
                self.cpp_info.components["headers"].defines = ["MY_MATRIX_HEADERS_DEFINE=1"]
                # Few flags to cover that CMakeDeps doesn't crash with them
                if self.settings.compiler == "msvc":
                    self.cpp_info.components["headers"].cxxflags = ["/Zc:__cplusplus"]
                    self.cpp_info.components["headers"].cflags = ["/Zc:__cplusplus"]
                    self.cpp_info.components["headers"].system_libs = ["ws2_32"]
                else:
                    self.cpp_info.components["headers"].system_libs = ["m"]
                    # Just to verify CMake don't break
                    self.cpp_info.sharedlinkflags = ["-z now", "-z relro"]
                    self.cpp_info.exelinkflags = ["-z now", "-z relro"]

                self.cpp_info.components["vector"].libs = ["vector"]
                self.cpp_info.components["vector"].includedirs = ["include"]
                self.cpp_info.components["vector"].libdirs = ["lib"]

                self.cpp_info.components["module"].libs = ["module"]
                self.cpp_info.components["module"].includedirs = ["include"]
                self.cpp_info.components["module"].libdirs = ["lib"]
                self.cpp_info.components["module"].requires = ["vector"]
          """)

    cmakelists = textwrap.dedent("""
       set(CMAKE_CXX_COMPILER_WORKS 1)
       set(CMAKE_CXX_ABI_COMPILED 1)
       cmake_minimum_required(VERSION 3.15)
       project(matrix CXX)

       add_library(vector src/vector.cpp)
       add_library(module src/module.cpp)
       add_library(headers INTERFACE)
       target_link_libraries(module PRIVATE vector)

       set_target_properties(headers PROPERTIES PUBLIC_HEADER "src/headers.h")
       set_target_properties(module PROPERTIES PUBLIC_HEADER "src/module.h")
       set_target_properties(vector PROPERTIES PUBLIC_HEADER "src/vector.h")
       install(TARGETS vector module)
       install(TARGETS headers PUBLIC_HEADER DESTINATION include/headers)
       """)
    c.save({"src/headers.h": headers_h,
            "src/vector.h": vector_h,
            "src/vector.cpp": vector_cpp,
            "src/module.h": module_h,
            "src/module.cpp": module_cpp,
            "CMakeLists.txt": cmakelists,
            "conanfile.py": conanfile})
    c.run("create .")
    return c


@pytest.fixture()
def matrix_client_components(_matrix_client_components):
    c = TestClient()
    c.cache_folder = os.path.join(temp_folder(), ".conan2")
    shutil.copytree(_matrix_client_components.cache_folder, c.cache_folder)
    return c


@pytest.fixture(scope="session")
def _matrix_c_interface_client():
    c = TestClient()
    matrix_h = textwrap.dedent("""\
        #pragma once
        #ifdef __cplusplus
        extern "C" {
        #endif
            void matrix();
        #ifdef __cplusplus
        }
        #endif
        """)
    matrix_cpp = textwrap.dedent("""\
        #include "matrix.h"
        #include <iostream>
        #include <string>
        void matrix(){
            std::cout<< std::string("Hello Matrix!") <<std::endl;
        }
        """)
    # Having here the config.cmake code to be able to manually check what CMake generates
    cmake = textwrap.dedent("""\
        cmake_minimum_required(VERSION 3.15)
        project(matrix C CXX)
        add_library(matrix STATIC src/matrix.cpp)
        target_include_directories(matrix PUBLIC
          $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
          $<INSTALL_INTERFACE:include>
        )
        set_target_properties(matrix PROPERTIES PUBLIC_HEADER "include/matrix.h")
        install(TARGETS matrix EXPORT matrixConfig)
        export(TARGETS matrix
            NAMESPACE matrix::
            FILE "${CMAKE_CURRENT_BINARY_DIR}/matrixConfig.cmake"
        )
        install(EXPORT matrixConfig
            DESTINATION "${CMAKE_INSTALL_PREFIX}/matrix/cmake"
            NAMESPACE matrix::
        )
        """)
    conanfile = textwrap.dedent("""\
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout
        class Recipe(ConanFile):
            name = "matrix"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            package_type = "static-library"
            generators = "CMakeToolchain"
            exports_sources = "CMakeLists.txt", "src/*", "include/*"
            languages = "C++"
            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
            def layout(self):
                cmake_layout(self)
            def package(self):
                cmake = CMake(self)
                cmake.install()
            def package_info(self):
                self.cpp_info.libs = ["matrix"]
        """)
    c.save({"include/matrix.h": matrix_h,
            "src/matrix.cpp": matrix_cpp,
            "conanfile.py": conanfile,
            "CMakeLists.txt": cmake})
    c.run("create .")
    return c


@pytest.fixture()
def matrix_c_interface_client(_matrix_c_interface_client):
    c = TestClient()
    c.cache_folder = os.path.join(temp_folder(), ".conan2")
    shutil.copytree(_matrix_c_interface_client.cache_folder, c.cache_folder)
    return c
