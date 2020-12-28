import textwrap
import unittest

from parameterized import parameterized

from conans.test.utils.tools import TestClient


class MultiGeneratorsTestCase(unittest.TestCase):

    @parameterized.expand([("cmake_find_package_multi",),
                           ("visual_studio_multi", ),
                           ("cmake_multi", )])
    def test_no_build_type(self, generator):
        client = TestClient()

        conanfile = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                settings = "os", "arch", "compiler"
                generators = "{generator}"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
        """.format(generator=generator))

        client.save({"conanfile.py": conanfile})
        client.run('install . -s compiler="Visual Studio"'
                   ' -s compiler.version=15 -s compiler.toolset=v100', assert_error=True)
        self.assertIn("ERROR: 'settings.build_type' doesn't exist", client.out)
