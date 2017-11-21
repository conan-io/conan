import unittest
from conans.test.utils.tools import TestClient


class CMakeInstallPackageTest(unittest.TestCase):

    def new_gcc_version_policy_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile, CMake
class AConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    exports_sources = "CMakeLists.txt", "*.h"
    generators = "cmake"
    def build(self):
        cmake = CMake(self)
        cmake.configure()
"""
        cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
project(Chat CXX)
cmake_minimum_required(VERSION 2.8.12)
include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()
"""
        client.save({"conanfile.py": conanfile,

                     "CMakeLists.txt": cmake})
        client.run("create Pkg/0.1@user/channel -s compiler=gcc -s compiler.version=7 "
                   "-s compiler.libcxx=libstdc++")
        print client.out


    def install_package_test(self):
        return
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
        client.run("create user/channel")
        self.assertIn("Test/0.1@user/channel test package: Content: my header h!!",
                      client.user_io.out)
