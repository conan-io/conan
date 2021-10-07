import os
import unittest

import pytest

from conans import tools
from conans.client.runner import ConanRunner
from conans.test.utils.tools import TestClient
from conans.test.utils.mocks import TestBufferConanOutput

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


@pytest.mark.tool_cmake
class CMakeGeneratorTest(unittest.TestCase):

    def _check_build_generator(self, os_build, generator):
        output = TestBufferConanOutput()
        runner = ConanRunner(True, False, True, output=output)
        client = TestClient(runner=runner)
        client.save({"conanfile.py": CONAN_RECIPE,
                     "CMakeLists.txt": CMAKE_RECIPE,
                     "dummy.cpp": CPP_CONTENT,
                     "my_profile": PROFILE.format(os_build=os_build)
                     })
        client.run("install . -pr my_profile")
        client.run("build .")

        if generator:
            self.assertIn('cmake -G "{}"'.format(generator), output)
            self.assertTrue(os.path.isfile(os.path.join(client.current_folder, "Makefile")))
        else:
            self.assertNotIn("cmake -G", output)
            self.assertFalse(os.path.isfile(os.path.join(client.current_folder, "Makefile")))

    @pytest.mark.skipif(not tools.os_info.is_linux, reason="Compilation with real gcc needed")
    def test_cmake_default_generator_linux(self):
        self._check_build_generator("Linux", "Unix Makefiles")

    @pytest.mark.skipif(not tools.os_info.is_windows, reason="Windows does not support default compiler")
    def test_cmake_default_generator_windows(self):
        self._check_build_generator("Windows", None)

    @pytest.mark.skipif(not tools.os_info.is_macos, reason="Compilation with real clang is needed")
    def test_cmake_default_generator_osx(self):
        self._check_build_generator("Macos", "Unix Makefiles")
