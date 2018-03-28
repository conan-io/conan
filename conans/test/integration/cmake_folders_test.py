import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import load, mkdir
import os
from parameterized import parameterized


class CMakeFoldersTest(unittest.TestCase):

    @parameterized.expand([(True, True), (False, True), (True, False), (False, False)])
    def basic_test(self, no_copy_source, cmake_install):
        client = TestClient()
        if not cmake_install:
            package_code = """
    def package(self):
        self.copy("*.h", src="src", dst="include")
"""
        else:
            package_code = "cmake.install()"

        conanfile = """from conans import ConanFile, CMake, load
import os
class Conan(ConanFile):
    settings = "os", "compiler", "arch", "build_type"
    exports_sources = "src/*"
    no_copy_source = {}
    def build(self):
        cmake = CMake(self)
        cmake.configure(source_folder="src",
                        cache_build_folder="build")
        cmake.build()
        {}

    def package_info(self):
        self.output.info("HEADER %s" % load(os.path.join(self.package_folder, "include/header.h")))
    """.format(no_copy_source, package_code)
        cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
project(Chat NONE)
cmake_minimum_required(VERSION 2.8.12)
file(READ header.h MYCONTENTS)
message(STATUS "HEADER CMAKE CONTENTS ${MYCONTENTS}")
install(FILES header.h DESTINATION include)
"""
        client.save({"conanfile.py": conanfile,
                     "src/CMakeLists.txt": cmake,
                     "src/header.h": "//myheader.h"})
        client.run("create . Hello/0.1@lasote/channel")
        self.assertIn("Hello/0.1@lasote/channel: HEADER //myheader.h", client.out)
        self.assertIn("-- HEADER CMAKE CONTENTS //myheader.h", client.out)
        # Now local flow
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        client.current_folder = build_folder
        client.run("install ..")
        client.run("build ..")  # same as --build-folder=. --source-folder=..
        self.assertIn("-- HEADER CMAKE CONTENTS //myheader.h", client.out)
        if not cmake_install:
            client.run("package ..")  # same as --build-folder=. --source-folder=..
        self.assertTrue(os.path.exists(os.path.join(build_folder, "conaninfo.txt")))
        self.assertTrue(os.path.exists(os.path.join(build_folder, "conanbuildinfo.txt")))
        self.assertEqual(load(os.path.join(build_folder, "package/include/header.h")), "//myheader.h")
