import unittest
from conans.test.utils.tools import TestClient


class CMakeInstallPackageTest(unittest.TestCase):

    def patch_config_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile, CMake
from conans.tools import save, load
import os
import platform

def _mess_with_path(pathstr):
   if platform.system() == "Windows":
       drive, path = os.path.splitdrive(pathstr)
       return drive.upper() + path.replace(os.path.sep,"/")
   return pathstr

class AConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    def build(self):
        cmake = CMake(self)
        pth = _mess_with_path(self.package_folder)
        self.output.info("output path: %s" % pth)
        save("file1.cmake", "FOLDER " + pth)
        save("sub/file1.cmake", "FOLDER " + pth)
        cmake.patch_config_paths()
    def package(self):
        self.copy("*")
        self.output.info("RESULT: " + load(os.path.join(self.package_folder, "file1.cmake")))
        self.output.info("RESULT2: " + load(os.path.join(self.package_folder, "sub/file1.cmake")))
"""

        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/channel")
        self.assertIn("Pkg/0.1@user/channel: RESULT: FOLDER ${CONAN_PKG_ROOT}", client.out)
        self.assertIn("Pkg/0.1@user/channel: RESULT2: FOLDER ${CONAN_PKG_ROOT}", client.out)

        client.run("install .")
        error = client.run("build .", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ConanException: cmake.patch_config_paths() can't work without package name",
                      client.out)

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

        client.run("create . user/channel")
        self.assertIn("Test/0.1@user/channel (test package): Content: my header h!!",
                      client.user_io.out)

        # Test also recipe without settings
        new_conanfile =\
            conanfile.replace("settings = \"os\", \"compiler\", \"build_type\", \"arch\"", "")
        self.assertNotIn("settings = \"os\", \"compiler\", \"build_type\", \"arch\"", new_conanfile)
        client.save({"conanfile.py": new_conanfile})

        client.run("remove * --force")
        client.run("create . user/channel")
        self.assertIn("Test/0.1@user/channel (test package): Content: my header h!!",
                      client.user_io.out)
