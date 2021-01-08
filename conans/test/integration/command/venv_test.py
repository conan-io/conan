import textwrap
import unittest

from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient

cmake = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(mytool CXX)
    add_executable(mytool main.cpp)
    install(TARGETS mytool RUNTIME DESTINATION bin)
    """)

conanfile = textwrap.dedent("""
    import os
    from conans import ConanFile
    from conan.tools.cmake import CMake, CMakeToolchain

    class MyTool(ConanFile):
        name = "mytool"
        settings = "os", "arch", "compiler", "build_type"
        exports_sources = "CMakeLists.txt", "main.cpp"

        def generate(self):
            tc = CMakeToolchain(self)
            tc.preprocessor_definitions["VERSION"] = self.version
            tc.generate()

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()

        def package(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.install()
    """)


class VEnvCommandTest(unittest.TestCase):
    def test_basic(self):
        client = TestClient()

        with self.assertRaises(Exception):
            client.run("venv mytool/1.0@ -- mytool --version")

        main = gen_function_cpp(name="main", preprocessor=["VERSION"])
        client.save({"main.cpp": main,
                     "conanfile.py": conanfile,
                     "CMakeLists.txt": cmake})

        client.run("create . mytool/1.0@")

        client.run("venv mytool/1.0@ -- mytool --version")
        self.assertIn("VERSION: 1.0", client.out)
        with self.assertRaises(Exception):
            client.run("venv mytool/2.0@ -- mytool --version")

        client.run("create . mytool/2.0@")

        client.run("venv mytool/2.0@ -- mytool --version")
        self.assertIn("VERSION: 2.0", client.out)

        client.run("venv mytool/1.0@ -- mytool --version")
        self.assertIn("VERSION: 1.0", client.out)
