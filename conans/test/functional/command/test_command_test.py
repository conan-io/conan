import time
import unittest

import pytest

from conans.paths import CONANFILE
from conans.test.assets.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient


@pytest.mark.slow
class ConanTestTest(unittest.TestCase):

    @pytest.mark.tool_cmake
    def test_conan_test(self):
        conanfile = '''
from conans import ConanFile, CMake
import os

class HelloReuseConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    requires = "Hello0/0.1@lasote/stable"
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        self.run('cmake "%s" %s' % (self.source_folder, cmake.command_line))
        self.run("cmake --build . %s" % cmake.build_config)

    def test(self):
        # equal to ./bin/greet, but portable windows
        self.run(os.sep.join([".","bin", "greet"]))
        '''

        client = TestClient()
        files = cpp_hello_conan_files("Hello0", "0.1")
        print_build = 'self.output.warn("BUILD_TYPE=>%s" % self.settings.build_type)'
        files[CONANFILE] = files[CONANFILE].replace("def build(self):",
                                                    'def build(self):\n        %s' % print_build)

        # Add build_type setting
        files[CONANFILE] = files[CONANFILE].replace(', "arch"',
                                                    ', "arch", "build_type"')

        cmakelist = """set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
project(MyHello CXX)
cmake_minimum_required(VERSION 2.8)

include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
conan_basic_setup()

ADD_EXECUTABLE(greet main.cpp)
TARGET_LINK_LIBRARIES(greet ${CONAN_LIBS})
"""
        files["test_package/CMakeLists.txt"] = cmakelist
        files["test_package/conanfile.py"] = conanfile
        files["test_package/main.cpp"] = files["main.cpp"]
        client.save(files)
        client.run("create . lasote/stable -tf=None")
        time.sleep(1)  # Try to avoid windows errors in CI  (Cannot change permissions)
        client.run("test test_package Hello0/0.1@lasote/stable -s build_type=Release")
        self.assertIn('Hello Hello0', client.out)

        self.assertNotIn("WARN: conanenv.txt file not found", client.out)
        self.assertIn('Hello Hello0', client.out)
        client.run("test test_package Hello0/0.1@lasote/stable -s Hello0:build_type=Debug "
                   "-o Hello0:language=1 --build missing")
        self.assertIn('Hola Hello0', client.out)
        self.assertIn('BUILD_TYPE=>Debug', client.out)
