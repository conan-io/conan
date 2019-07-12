import os
import platform
import unittest

from nose.plugins.attrib import attr

from conans.client.tools import replace_in_file
from conans.test.utils.tools import TestClient


class CMakeGeneratorTest(unittest.TestCase):

    def test_no_check_compiler(self):
        # https://github.com/conan-io/conan/issues/4268
        file_content = '''from conans import ConanFile, CMake

class ConanFileToolsTest(ConanFile):
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
    '''

        cmakelists = '''cmake_minimum_required(VERSION 2.8)
PROJECT(conanzlib LANGUAGES NONE)
set(CONAN_DISABLE_CHECK_COMPILER TRUE)

include(conanbuildinfo.cmake)
CONAN_BASIC_SETUP()
'''
        client = TestClient()
        client.save({"conanfile.py": file_content,
                     "CMakeLists.txt": cmakelists})

        client.run('install .')
        client.run('build .')

    @attr("slow")
    @unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
    def skip_check_if_toolset_test(self):
        file_content = '''from conans import ConanFile, CMake

class ConanFileToolsTest(ConanFile):
    generators = "cmake"
    exports_sources = "CMakeLists.txt"
    settings = "os", "arch", "compiler"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()
    '''
        client = TestClient()
        cmakelists = '''
set(CMAKE_CXX_COMPILER_WORKS 1)
set(CMAKE_CXX_ABI_COMPILED 1)
PROJECT(Hello)
cmake_minimum_required(VERSION 2.8)
include("${CMAKE_BINARY_DIR}/conanbuildinfo.cmake")
CONAN_BASIC_SETUP()
'''
        client.save({"conanfile.py": file_content,
                     "CMakeLists.txt": cmakelists})
        client.run("create . lib/1.0@user/channel -s compiler='Visual Studio' -s compiler.toolset=v140")
        self.assertIn("Conan: Skipping compiler check: Declared 'compiler.toolset'", client.out)


    @attr('slow')
    def no_output_test(self):
        client = TestClient()
        client.run("new Test/1.0 --sources")
        cmakelists_path = os.path.join(client.current_folder, "src", "CMakeLists.txt")

        # Test output works as expected
        client.run("install .")
        # No need to do a full create, the build --configure is good
        client.run("build . --configure")
        self.assertIn("Conan: Using cmake global configuration", client.out)
        self.assertIn("Conan: Adjusting default RPATHs Conan policies", client.out)
        self.assertIn("Conan: Adjusting language standard", client.out)

        # Silence output
        replace_in_file(cmakelists_path,
                        "conan_basic_setup()",
                        "set(CONAN_CMAKE_SILENT_OUTPUT True)\nconan_basic_setup()",
                        output=client.out)
        client.run("build . --configure")
        self.assertNotIn("Conan: Using cmake global configuration", client.out)
        self.assertNotIn("Conan: Adjusting default RPATHs Conan policies", client.out)
        self.assertNotIn("Conan: Adjusting language standard", client.out)

        # Use TARGETS
        replace_in_file(cmakelists_path, "conan_basic_setup()", "conan_basic_setup(TARGETS)",
                        output=client.out)
        client.run("build . --configure")
        self.assertNotIn("Conan: Using cmake targets configuration", client.out)
        self.assertNotIn("Conan: Adjusting default RPATHs Conan policies", client.out)
        self.assertNotIn("Conan: Adjusting language standard", client.out)
