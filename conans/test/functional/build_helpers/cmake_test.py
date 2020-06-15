import textwrap
import unittest

from conans.test.utils.tools import TestClient


class CMakeBuildHelper(unittest.TestCase):
    def get_version_test(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
        from conans import ConanFile, CMake
        class Pkg(ConanFile):
            def build(self):
                self.output.info("CMAKE_VERSION: %s" % CMake.get_version())
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/0.1@user/testing")
        self.assertIn("CMAKE_VERSION: 3", client.out)

    def test_inheriting_cmake_build_helper(self):
        # https://github.com/conan-io/conan/issues/7196
        base = textwrap.dedent("""
            import conans
            class CMake(conans.CMake):
                pass
            class BaseConanFile(conans.ConanFile):
                pass
            """)
        client = TestClient()
        client.save({"conanfile.py": base})
        client.run("export . pkg/0.1@")
        self.assertIn("pkg/0.1: Exported revision", client.out)
