import unittest

from nose.plugins.attrib import attr

from conans import tools
from conans.test.utils.tools import TestClient


CONAN_RECIPE = """
from conans import ConanFile, CMake

class FooConan(ConanFile):
    name = "foo"
    version = "0.1"
    settings = "os_build", "compiler", "build_type"
    generators = "cmake"
    exports = '*'

    def build(self):
        cmake = CMake(self)
        cmake.configure()
"""


CPP_CONTENT = """
int main() {}
"""

CMAKE_RECIPE = """
cmake_minimum_required(VERSION 2.8.12)
project(dummy CXX)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()

add_executable(dummy dummy.cpp)
"""


@attr("slow")
class CMakeGeneratorTest(unittest.TestCase):

    def _generator_test_helper(self, os_build, makefile):
        try:
            client = TestClient()
            client.save({"conanfile.py": CONAN_RECIPE,
                        "CMakeLists.txt": CMAKE_RECIPE,
                        "dummy.cpp": CPP_CONTENT})
            client.run("create . lasote/testing -s os_build={}".format(os_build))
        finally:
            self.assertNotIn("TypeError: argument of type 'NoneType' is not iterable", client.user_io.out)
            self.assertNotIn("ERROR:", client.user_io.out)
            self.assertIn("Check for working CXX compiler", client.user_io.out)
            self.assertIn('cmake -G "{}"'.format(makefile), client.user_io.out)

    def test_cmake_default_generator_linux(self):
        self._generator_test_helper("Linux", "Unix Makefiles")

    @unittest.skipUnless(tools.os_info.is_windows, "MinGW is only supported on Windows")
    def test_cmake_default_generator_windows(self):
        self._generator_test_helper("Windows", "MinGW Makefiles")

    def test_cmake_default_generator_osx(self):
        self._generator_test_helper("Macos", "Unix Makefiles")
