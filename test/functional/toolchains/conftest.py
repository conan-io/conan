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
    vector_h = gen_function_h(name="vector")
    vector_cpp = gen_function_cpp(name="vector", includes=["vector"])
    module_h = gen_function_h(name="module")
    module_cpp = gen_function_cpp(name="module", includes=["module", "vector"], calls=["vector"])

    conanfile = textwrap.dedent("""
      from os.path import join
      from conan import ConanFile
      from conan.tools.cmake import CMake
      from conan.tools.files import copy

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
       target_link_libraries(module PRIVATE vector)

       set_target_properties(module PROPERTIES PUBLIC_HEADER "src/module.h")
       install(TARGETS vector module)
       """)
    c.save({"src/vector.h": vector_h,
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
