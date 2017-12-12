import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import load, mkdir
import os


class CMakeMesonFoldersTest(unittest.TestCase):

    def basic_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile, CMake, load
import os
class Conan(ConanFile):
    settings = "os", "compiler", "arch", "build_type"
    exports_sources = "src/*"
    no_copy_sources = True
    def build(self):
        cmake = CMake(self)
        cmake.configure(cache_source_dir="src",
                        cache_build_dir="build")
        cmake.build()
        cmake.install()

    def package_info(self):
        self.output.info("HEADER %s" % load(os.path.join(self.package_folder, "include/header.h")))
    """
        cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
project(Chat NONE)
cmake_minimum_required(VERSION 2.8.12)
install(FILES header.h DESTINATION include)
"""
        client.save({"conanfile.py": conanfile,
                     "src/CMakeLists.txt": cmake,
                     "src/header.h": "//myheader.h"})
        client.run("create Hello/0.1@lasote/channel")
        self.assertIn("Hello/0.1@lasote/channel: HEADER //myheader.h", client.out)
        # Now local flow
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        client.current_folder = build_folder
        client.run("install ..")
        client.run("build .. --build_folder=. --source_folder=../src")
        self.assertTrue(os.path.exists(os.path.join(build_folder, "conaninfo.txt")))
        self.assertTrue(os.path.exists(os.path.join(build_folder, "conanbuildinfo.txt")))
        self.assertEqual(load(os.path.join(build_folder, "package/include/header.h")), "//myheader.h")
