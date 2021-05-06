import textwrap
import unittest

from conans.test.utils.tools import TestClient


class MultiGeneratorsTestCase(unittest.TestCase):

    def test_no_build_type(self,):
        client = TestClient()

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                settings = "os", "arch", "compiler"
                generators = "CMakeDeps"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
        """)

        client.save({"conanfile.py": conanfile})
        client.run('install . -s compiler="Visual Studio"'
                   ' -s compiler.version=15 -s compiler.toolset=v100', assert_error=True)
        self.assertIn("ERROR: Error in generator 'CMakeDeps': 'settings.build_type' doesn't exist",
                      client.out)
