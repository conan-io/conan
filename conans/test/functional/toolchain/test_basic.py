# coding=utf-8
import platform
import textwrap
import unittest

import pytest
import six
from nose.plugins.attrib import attr

from conans.test.utils.tools import TestClient


@attr("toolchain")
@pytest.mark.toolchain
class BasicTest(unittest.TestCase):

    def test_basic(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.cmake import CMakeToolchain
            class Pkg(ConanFile):
                def toolchain(self):
                    tc = CMakeToolchain(self)
                    tc.write_toolchain_files()
                """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")

        self.assertIn("conanfile.py: Generating toolchain files", client.out)
        toolchain = client.load("conan_toolchain.cmake")
        self.assertIn("Conan automatically generated toolchain file", toolchain)

    def test_declarative(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                toolchain = "cmake"
                """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")

        self.assertIn("conanfile.py: Generating toolchain files", client.out)
        toolchain = client.load("conan_toolchain.cmake")
        self.assertIn("Conan automatically generated toolchain file", toolchain)

    def test_declarative_new_helper(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.cmake import CMake
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

    @unittest.skipIf(six.PY2, "The import to sibling fails in Python2")
    def test_old_cmake_tools_imports(self):
        conanfile = textwrap.dedent("""
           from conans import ConanFile, CMakeToolchain, CMake
           class Pkg(ConanFile):
               def toolchain(self):
                   tc = CMakeToolchain(self)
                   tc.write_toolchain_files()
               def build(self):
                   cmake = CMake(self)
                   cmake.configure()
           """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        self.assertIn("'from conans import CMakeToolchain' has been deprecated and moved",
                      client.out)
        client.run("build .", assert_error=True)  # No CMakeLists.txt
        self.assertIn("This 'CMake' build helper has been deprecated and moved.", client.out)
        self.assertIn('-DCMAKE_TOOLCHAIN_FILE="conan_toolchain.cmake"', client.out)
        self.assertIn("ERROR: conanfile.py: Error in build() method", client.out)

    @unittest.skipIf(six.PY2, "The import to sibling fails in Python2")
    @unittest.skipUnless(platform.system() == "Windows", "msbuild requires Windows")
    def test_old_msbuild_tools_imports(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, MSBuildToolchain, MSBuild
            class Pkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                def toolchain(self):
                   tc = MSBuildToolchain(self)
                   tc.write_toolchain_files()
                def build(self):
                   msbuild = MSBuild(self)
                   msbuild.build("Project.sln")
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        self.assertIn("'from conans import MSBuildToolchain' has been deprecated and moved",
                      client.out)
        client.run("build .", assert_error=True)  # No CMakeLists.txt
        self.assertIn("This 'MSBuild' build helper has been deprecated and moved.", client.out)
        self.assertIn("ERROR: conanfile.py: Error in build() method", client.out)

    @unittest.skipIf(six.PY2, "The import to sibling fails in Python2")
    def test_old_gnu_tools_imports(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, MakeToolchain
            class Pkg(ConanFile):
                settings = "os", "compiler", "arch", "build_type"
                def toolchain(self):
                   tc = MakeToolchain(self)
                   tc.write_toolchain_files()
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        self.assertIn("'from conans import MakeToolchain' has been deprecated and moved",
                      client.out)
