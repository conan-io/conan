import textwrap
import unittest

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.tool_cmake
class CMakeBuildHelper(unittest.TestCase):
    def test_get_version_no_toolchain(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake
        class Pkg(ConanFile):
            def build(self):
                self.output.info("CMAKE_VERSION: %s" % CMake.get_version())
                cmake = CMake(self)
                self.output.info("CMAKE_VERSION (obj): %s" % cmake.get_version())
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/0.1@user/testing")
        self.assertIn("CMAKE_VERSION: 3", client.out)
        self.assertIn("CMAKE_VERSION (obj): 3", client.out)

    def test_get_version_toolchain(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake
        class Pkg(ConanFile):

            def build(self):
                self.output.info("CMAKE_VERSION: %s" % CMake.get_version())
                cmake = CMake(self)
                self.output.info("CMAKE_VERSION (obj): %s" % cmake.get_version())
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/0.1@user/testing")
        self.assertIn("CMAKE_VERSION: 3", client.out)
        self.assertIn("CMAKE_VERSION (obj): 3", client.out)
