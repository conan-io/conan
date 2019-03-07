import os
import unittest

from conans import tools
from conans.test.utils.tools import TestClient


CONAN_RECIPE = """
from conans import ConanFile, CMake

class FooConan(ConanFile):
    name = "foo"
    version = "0.1"
    settings = "os_build"
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
"""


CPP_CONTENT = """
int main() {}
"""

CMAKE_RECIPE = """
cmake_minimum_required(VERSION 2.8.12)
project(dummy)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()
"""

PROFILE = """
[settings]
os={os_build}
os_build={os_build}
"""


class CMakeGeneratorTest(unittest.TestCase):

    def _check_build_generator(self, os_build, generator):
        client = TestClient()
        client.save({"conanfile.py": CONAN_RECIPE,
                     "CMakeLists.txt": CMAKE_RECIPE,
                     "dummy.cpp": CPP_CONTENT,
                     "my_profile": PROFILE.format(os_build=os_build)
                     })
        client.run("install . -p my_profile")
        client.run("build .")

        if generator:
            self.assertIn('cmake -G "{}"'.format(generator), client.out)
            self.assertTrue(os.path.isfile(os.path.join(client.current_folder, "Makefile")))
        else:
            self.assertNotIn("cmake -G", client.out)
            self.assertFalse(os.path.isfile(os.path.join(client.current_folder, "Makefile")))

    @unittest.skipUnless(tools.os_info.is_linux, "Compilation with real gcc needed")
    def test_cmake_default_generator_linux(self):
        self._check_build_generator("Linux", "Unix Makefiles")

    @unittest.skipUnless(tools.os_info.is_windows, "Windows does not support default compiler")
    def test_cmake_default_generator_windows(self):
        self._check_build_generator("Windows", None)

    @unittest.skipUnless(tools.os_info.is_macos, "Compilation with real clang is needed")
    def test_cmake_default_generator_osx(self):
        self._check_build_generator("Macos", "Unix Makefiles")
