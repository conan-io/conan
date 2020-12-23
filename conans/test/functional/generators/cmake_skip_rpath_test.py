import platform
import unittest

import pytest

from conans.test.utils.tools import TestClient

conanfile_py = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"

"""

conanfile = """[requires]
Hello/0.1@lasote/testing
"""

cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8.12)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup(TARGETS %s)

IF(APPLE AND CMAKE_SKIP_RPATH)
    MESSAGE(FATAL_ERROR "RPath was skipped")
ENDIF()
"""


@pytest.mark.tool_cmake
class CMakeSkipRpathTest(unittest.TestCase):

    def test_skip_flag(self):
        for way_to_skip in ("SKIP_RPATH", "KEEP_RPATHS"):
            client = TestClient()
            client.save({"conanfile.py": conanfile_py})
            client.run("export . lasote/testing")
            client.save({"conanfile.txt": conanfile,
                         "CMakeLists.txt": cmake % way_to_skip}, clean_first=True)
            client.run('install . -g cmake --build')
            generator = '-G "Visual Studio 15 Win64"' if platform.system() == "Windows" else ""
            client.run_command("cmake . %s" % generator)
            self.assertNotIn("Conan: Adjusting default RPATHs Conan policies", client.out)
            self.assertIn("Build files have been written", client.out)
            if way_to_skip == "SKIP_RPATH":
                self.assertIn("Conan: SKIP_RPATH is deprecated, it has been renamed to KEEP_RPATHS",
                              client.out)

            client.save({"conanfile.txt": conanfile,
                         "CMakeLists.txt": (cmake % way_to_skip).replace("TARGETS", "")},
                        clean_first=True)

            client.run('install . -g cmake --build')
            client.run_command("cmake . %s" % generator)
            self.assertNotIn("Conan: Adjusting default RPATHs Conan policies", client.out)
            self.assertIn("Build files have been written", client.out)

            client.save({"conanfile.txt": conanfile,
                         "CMakeLists.txt": (cmake % "").replace("FATAL_ERROR", "INFO")},
                        clean_first=True)

            if platform.system() == "Darwin":
                client.run('install . -g cmake --build')
                client.run_command("cmake .")
                self.assertIn("Conan: Adjusting default RPATHs Conan policies", client.out)
                self.assertIn("Build files have been written", client.out)
                self.assertIn("RPath was skipped", client.out)
