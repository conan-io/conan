import unittest
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
conan_basic_setup(TARGETS SKIP_RPATH)

IF(APPLE AND CMAKE_SKIP_RPATH)
    MESSAGE(FATAL_ERROR "RPath was not skipped")
ENDIF()
"""


class CMakeSkipRpathTest(unittest.TestCase):

    def test_skip_flag(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile_py})
        client.run("export lasote/testing")
        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake}, clean_first=True)

        client.run('install -g cmake --build')
        client.runner("cmake .", cwd=client.current_folder)
        self.assertNotIn("Conan: Adjusting default RPATHs Conan policies", client.user_io.out)
        self.assertIn("Build files have been written", client.user_io.out)

        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake.replace("TARGETS SKIP_RPATH", "SKIP_RPATH")},
                    clean_first=True)

        client.run('install -g cmake --build')
        client.runner("cmake .", cwd=client.current_folder)
        self.assertNotIn("Conan: Adjusting default RPATHs Conan policies", client.user_io.out)
        self.assertIn("Build files have been written", client.user_io.out)

        client.save({"conanfile.txt": conanfile,
                     "CMakeLists.txt": cmake.replace("SKIP_RPATH", "")},
                    clean_first=True)

        client.run('install -g cmake --build')
        client.runner("cmake .", cwd=client.current_folder)
        self.assertIn("Conan: Adjusting default RPATHs Conan policies", client.user_io.out)
        self.assertIn("Build files have been written", client.user_io.out)
