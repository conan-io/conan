import os
import subprocess
import unittest

from conans.test.utils.tools import TestClient
from nose.plugins.attrib import attr


hello_cpp = """
#include <iostream>
#include "hello.h"

void hello(){
    std::cout << "Hello World!" << std::endl;
}
"""

hello_h = "void hello();"

conanfile = """
from conans import ConanFile, CMake


class HelloConan(ConanFile):
    name = "hello"
    version = "1.0"
    exports_sources = "hello/*"
    settings = "os", "compiler", "arch", "build_type"
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        cmake.insert_conan_build_info("hello")
        cmake.configure()
        cmake.build()

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

cmake = """
cmake_minimum_required(VERSION 2.8)
PROJECT(MyHello)
ADD_LIBRARY(hello hello.cpp)
"""


@attr("slow")
class CMakeFlagsTest(unittest.TestCase):

    def insert_build_create_test(self):
        client = TestClient()
        client.run("new Hello/1.0 -t")
        client.save({"conanfile.py": conanfile,
                     "hello/hello.h": hello_h,
                     "hello/hello.cpp": hello_cpp,
                     "hello/CMakeLists.txt": cmake
                     })
        client.run("create . danimtb/testing")
        self.assertIn("Conan: called by CMake conan helper", client.out)

    def insert_source_create_test(self):
        client = TestClient()
        client.run("new Hello/1.0 -t")
        conanfile_source = conanfile.replace("cmake.insert_conan_build_info(\"hello\")", "")
        source_insert = """generators = "cmake"

    def source(self):
        CMake.insert_conan_build_info("hello")
"""
        conanfile_source = conanfile_source.replace("generators = \"cmake\"", source_insert)
        client.save({"conanfile.py": conanfile_source,
                     "hello/hello.h": hello_h,
                     "hello/hello.cpp": hello_cpp,
                     "hello/CMakeLists.txt": cmake
                     })
        client.run("create . danimtb/testing")
        self.assertIn("Conan: called by CMake conan helper", client.out)

    def insert_build_dev_test(self):
        client = TestClient()
        client.run("new Hello/1.0 -t")
        client.save({"conanfile.py": conanfile,
                     "hello/hello.h": hello_h,
                     "hello/hello.cpp": hello_cpp,
                     "hello/CMakeLists.txt": cmake
                     })
        client.run("install .")
        client.run("build . ")
        self.assertIn("Conan: called by CMake conan helper", client.out)

    def insert_build_dev_folder_test(self):
        client = TestClient()
        client.run("new Hello/1.0 -t")
        client.save({"conanfile.py": conanfile,
                     "hello/hello.h": hello_h,
                     "hello/hello.cpp": hello_cpp,
                     "hello/CMakeLists.txt": cmake
                     })
        client.run("install . -if build")
        error = client.run("build . -bf build -sf .", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("does not appear to contain CMakeLists.txt", client.out)
        self.assertTrue(
            os.path.exists(os.path.join(client.current_folder, "build", "CMakeLists.txt")))
        self.assertFalse(
            os.path.exists(os.path.join(client.current_folder, "CMakeLists.txt")))
        error = client.run("build . -bf build -sf build", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("add_subdirectory given source \"hello\" which is not an existing directory",
                      client.out)

    def insert_source_dev_test(self):
        client = TestClient()
        client.run("new Hello/1.0 -t")
        conanfile_source = conanfile.replace("cmake.insert_conan_build_info(\"hello\")", "")
        source_insert = """generators = "cmake"

    def source(self):
        CMake.insert_conan_build_info("hello")
"""
        conanfile_source = conanfile_source.replace("generators = \"cmake\"", source_insert)
        client.save({"conanfile.py": conanfile_source,
                     "hello/hello.h": hello_h,
                     "hello/hello.cpp": hello_cpp,
                     "hello/CMakeLists.txt": cmake
                     })
        client.run("source .")
        client.run("install .")
        client.run("build .")
        self.assertIn("Conan: called by CMake conan helper", client.out)

    def insert_source_dev_folder_test(self):
        client = TestClient()
        client.run("new Hello/1.0 -t")
        conanfile_source = conanfile.replace("cmake.insert_conan_build_info(\"hello\")", "")
        source_insert = """generators = "cmake"

    def source(self):
        CMake.insert_conan_build_info("hello")
"""
        conanfile_source = conanfile_source.replace("generators = \"cmake\"", source_insert)
        client.save({"conanfile.py": conanfile_source,
                     "hello/hello.h": hello_h,
                     "hello/hello.cpp": hello_cpp,
                     "hello/CMakeLists.txt": cmake
                     })
        client.run("source .")
        client.run("install . -if build")
        client.run("build . -bf build -sf .")
        self.assertIn("Conan: called by CMake conan helper", client.out)
