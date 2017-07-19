import unittest
from conans.test.utils.tools import TestClient


class CMakeInstallPackageTest(unittest.TestCase):

    def install_package_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile, CMake

class AConan(ConanFile):
    name = "Test"
    version = "0.1"
    settings = "os", "compiler", "build_type", "arch"
    exports_sources = "CMakeLists.txt", "*.h"
    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.install()
"""
        test_conanfile = """from conans import ConanFile, load

class TestConan(ConanFile):
    requires = "Test/0.1@user/channel"
    def imports(self):
        self.copy("*.h", "myimports")
    def test(self):
        self.output.info("Content: %s" % load("myimports/include/header.h"))

        """
        cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
project(Chat NONE)
cmake_minimum_required(VERSION 2.8.12)

        install(FILES header.h DESTINATION include)
"""
        client.save({"conanfile.py": conanfile,
                     "test/conanfile.py": test_conanfile,
                     "CMakeLists.txt": cmake,
                     "header.h": "my header h!!"})
        client.run("test_package")
        self.assertIn("Test/0.1@user/channel test package: Content: my header h!!",
                      client.user_io.out)
