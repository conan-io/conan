# coding=utf-8
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.test.utils.tools import TestClient


@attr("toolchain")
class BasicTest(unittest.TestCase):

    def test_basic(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMakeToolchain
            class Pkg(ConanFile):
                def toolchain(self):
                    return CMakeToolchain(self)
                """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")

        self.assertIn("conanfile.py: Generating toolchain files", client.out)
        toolchain = client.load("conan_toolchain.cmake")
        self.assertIn("cmake_minimum_required", toolchain)

    def test_declarative(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMakeToolchain
            class Pkg(ConanFile):
                toolchain = "cmake"
                """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")

        self.assertIn("conanfile.py: Generating toolchain files", client.out)
        toolchain = client.load("conan_toolchain.cmake")
        self.assertIn("cmake_minimum_required", toolchain)

    def test_declarative_new_helper(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake
            class Pkg(ConanFile):
                toolchain = "cmake"
                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        client.run("build .", assert_error=True)  # No CMakeLists.txt
        self.assertIn('-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"',  client.out)
        self.assertIn("ERROR: conanfile.py: Error in build() method", client.out)
