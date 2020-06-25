import textwrap
import unittest

from conans.test.utils.tools import TestClient


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
            toolchain = "cmake"

            def build(self):
                self.output.info("CMAKE_VERSION: %s" % CMake.get_version())
                cmake = CMake(self)
                self.output.info("CMAKE_VERSION (obj): %s" % cmake.get_version())
        """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/0.1@user/testing")
        self.assertIn("CMAKE_VERSION: 3", client.out)
        self.assertIn("CMAKE_VERSION (obj): 3", client.out)

    def test_inheriting_cmake_build_helper_no_toolchain(self):
        # https://github.com/conan-io/conan/issues/7196
        base = textwrap.dedent("""
            import conans
            class CMake(conans.CMake):
                pass
            class BaseConanFile(conans.ConanFile):
                def build(self):
                    self.output.info("CMAKE_VERSION: %s" % conans.CMake.get_version())
                    cmake = CMake(self)
                    self.output.info("CMAKE_VERSION (obj): %s" % cmake.get_version())
        """)

        client = TestClient()
        client.save({"conanfile.py": base})
        client.run("create . pkg/0.1@")
        self.assertIn("pkg/0.1: Exported revision", client.out)
        self.assertIn("CMAKE_VERSION: 3", client.out)
        self.assertIn("CMAKE_VERSION (obj): 3", client.out)

    def test_inheriting_cmake_build_helper_toolchain(self):
        # https://github.com/conan-io/conan/issues/7196
        base = textwrap.dedent("""
            import conans
            class CMake(conans.CMake):
                pass
            class BaseConanFile(conans.ConanFile):
                toolchain = "cmake"
                def build(self):
                    self.output.info("CMAKE_VERSION: %s" % conans.CMake.get_version())
                    cmake = CMake(self)
                    self.output.info("CMAKE_VERSION (obj): %s" % cmake.get_version())
        """)

        client = TestClient()
        client.save({"conanfile.py": base})
        client.run("create . pkg/0.1@")
        self.assertIn("pkg/0.1: Exported revision", client.out)
        self.assertIn("CMAKE_VERSION: 3", client.out)
        self.assertIn("CMAKE_VERSION (obj): 3", client.out)
