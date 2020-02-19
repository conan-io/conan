import platform
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


@unittest.skipUnless(platform.system() == "Darwin", "Only for MacOS")
class CMakeAppleFrameworksTestCase(unittest.TestCase):
    lib_ref = ConanFileReference.loads("lib/version")
    lib_conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Lib(ConanFile):
            def package_info(self):
                self.cpp_info.frameworks.extend(['Foundation', 'CoreServices', 'CoreFoundation'])
    """)

    app_conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake

        class App(ConanFile):
            requires = "{}"
            generators = "{{generator}}"
            
            def build(self):
                cmake = CMake(self)
                cmake.configure()
    """.format(lib_ref))

    def setUp(self):
        self.t = TestClient()
        self.t.save({'conanfile.py': self.lib_conanfile})
        self.t.run("create . {}@".format(self.lib_ref))

    def _check_frameworks_found(self, output):
        self.assertIn("/System/Library/Frameworks/Foundation.framework;", output)
        self.assertIn("/System/Library/Frameworks/CoreServices.framework;", output)
        self.assertIn("/System/Library/Frameworks/CoreFoundation.framework", output)

    def test_apple_framework_cmake(self):
        app_cmakelists = textwrap.dedent("""
            project(Testing CXX)

            include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
            conan_basic_setup()
            
            message(">>> CONAN_FRAMEWORKS_FOUND_LIB: ${CONAN_FRAMEWORKS_FOUND_LIB}")
        """)

        self.t.save({'conanfile.py': self.app_conanfile.format(generator="cmake"),
                     'CMakeLists.txt': app_cmakelists})
        self.t.run("install .")
        self.t.run("build .")
        self._check_frameworks_found(str(self.t.out))

    def test_apple_framework_cmake_find_package(self):
        app_cmakelists = textwrap.dedent("""
            project(Testing CXX)

            find_package(lib)
            
            message(">>> CONAN_FRAMEWORKS_FOUND_LIB: ${lib_FRAMEWORKS_FOUND}")
        """)

        self.t.save({'conanfile.py': self.app_conanfile.format(generator="cmake_find_package"),
                     'CMakeLists.txt': app_cmakelists})
        self.t.run("install .")
        self.t.run("build .")
        self._check_frameworks_found(str(self.t.out))
