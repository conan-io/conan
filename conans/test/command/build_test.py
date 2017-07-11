from conans.test.utils.tools import TestClient
import unittest
from conans.paths import CONANFILE
from conans.model.ref import PackageReference
import os
from conans.util.files import load


conanfile_scope_env = """
from conans import ConanFile

class AConan(ConanFile):
    requires = "Hello/0.1@lasote/testing"
    generators = "cmake"

    def build(self):
        self.output.info("INCLUDE PATH: %s" % self.deps_cpp_info.include_paths[0])
        self.output.info("HELLO ROOT PATH: %s" % self.deps_cpp_info["Hello"].rootpath)
        self.output.info("HELLO INCLUDE PATHS: %s" % self.deps_cpp_info["Hello"].include_paths[0])
"""

conanfile_dep = """
from conans import ConanFile

class AConan(ConanFile):
    name = "Hello"
    version = "0.1"
"""


class ConanBuildTest(unittest.TestCase):

    def build_error_test(self):
        """ If not using -g txt generator, and build() requires self.deps_cpp_info,
        or self.deps_user_info it will fail
        """
        client = TestClient()
        client.save({CONANFILE: conanfile_dep})
        client.run("export lasote/testing")
        client.save({CONANFILE: conanfile_scope_env}, clean_first=True)
        client.run("install --build=missing")
        error = client.run("build", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: PROJECT: Error in build() method, line 9", client.user_io.out)
        self.assertIn("self.deps_cpp_info not defined", client.user_io.out)

        conanfile_user_info = """
from conans import ConanFile

class AConan(ConanFile):
    requires = "Hello/0.1@lasote/testing"
    generators = "cmake"

    def build(self):
        self.deps_user_info.VAR
"""
        client.save({CONANFILE: conanfile_user_info}, clean_first=True)
        client.run("install --build=missing")
        error = client.run("build", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: PROJECT: Error in build() method, line 9", client.user_io.out)
        self.assertIn("self.deps_user_info not defined", client.user_io.out)

    def build_test(self):
        """ Try to reuse variables loaded from txt generator => deps_cpp_info
        """
        client = TestClient()
        client.save({CONANFILE: conanfile_dep})
        client.run("export lasote/testing")

        client.save({CONANFILE: conanfile_scope_env}, clean_first=True)
        client.run("install --build=missing -g txt")

        client.run("build")
        ref = PackageReference.loads("Hello/0.1@lasote/testing:"
                                     "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = client.paths.package(ref).replace("\\", "/")
        self.assertIn("Project: INCLUDE PATH: %s/include" % package_folder, client.user_io.out)
        self.assertIn("Project: HELLO ROOT PATH: %s" % package_folder, client.user_io.out)
        self.assertIn("Project: HELLO INCLUDE PATHS: %s/include"
                      % package_folder, client.user_io.out)

    def build_cmake_install_test(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile, CMake

class AConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.install()
"""
        cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
project(Chat NONE)
cmake_minimum_required(VERSION 2.8.12)

        install(FILES header.h DESTINATION include)
"""
        client.save({CONANFILE: conanfile,
                     "CMakeLists.txt": cmake,
                     "header.h": "my header h!!"})
        client.run("install")
        error = client.run("build", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("CMAKE_INSTALL_PREFIX not defined for 'cmake.install()'",
                      client.user_io.out)
        client.run("build -pf=mypkg")
        header = load(os.path.join(client.current_folder, "mypkg/include/header.h"))
        self.assertEqual(header, "my header h!!")
