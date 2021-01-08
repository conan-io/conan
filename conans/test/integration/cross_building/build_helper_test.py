import textwrap
import unittest

from conans.test.utils.tools import TestClient


class BuildHelperTest(unittest.TestCase):
    def test_autotools_helper(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, AutoToolsBuildEnvironment

            class Pkg(ConanFile):
                def build(self):
                    AutoToolsBuildEnvironment(self)

        """)
        client.save({"conanfile.py": conanfile,
                     "host": "",
                     "build": ""})
        client.run("create . pkg/1.0@ --profile:build=build --profile:host=host")
        self.assertIn("Configuration (profile_host):", client.out)
        self.assertIn("Configuration (profile_build):", client.out)
        self.assertIn("pkg/1.0: Calling build()", client.out)
        self.assertIn("pkg/1.0: Created package", client.out)
