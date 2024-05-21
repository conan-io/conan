import os
import shutil
import textwrap

import pytest

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

            languages = "C", "C++"

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
