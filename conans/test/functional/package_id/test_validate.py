import textwrap
import unittest

from conans.cli.exit_codes import ERROR_INVALID_CONFIGURATION
from conans.test.utils.tools import TestClient


class TestValidate(unittest.TestCase):

    def test_validate_create(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.errors import ConanInvalidConfiguration
            class Pkg(ConanFile):
                settings = "os"

                def package_id(self):
                    if self.settings.os == "Windows":
                        self.info.invalid = "Windows not supported"
            """)

        client.save({"conanfile.py": conanfile})

        client.run("create . pkg/0.1@ -s os=Linux")
        self.assertIn("pkg/0.1: Package 'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31' created",
                      client.out)

        error = client.run("create . pkg/0.1@ -s os=Windows", assert_error=True)
        print(client.out)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("ERROR: pkg/0.1: Invalid ID: Windows not supported", client.out)
        client.run("info pkg/0.1@ -s os=Windows")
        print(client.out)
        self.assertIn("ID: INVALID", client.out)

    def test_validate_compatible(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conans.errors import ConanInvalidConfiguration
            class Pkg(ConanFile):
                settings = "os"

                def package_id(self):
                    if self.settings.os == "Windows":
                        compatible_pkg = self.info.clone()
                        compatible_pkg.settings.os = "Linux"
                        self.compatible_packages.append(compatible_pkg)
                        self.info.invalid = "Windows not supported"

            """)

        client.save({"conanfile.py": conanfile})

        client.run("create . pkg/0.1@ -s os=Linux")
        self.assertIn("pkg/0.1: Package 'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31' created",
                      client.out)

        client.run("create . pkg/0.1@ -s os=Windows")
        print(client.out)
        self.assertIn("pkg/0.1: Main binary package 'INVALID' missing. "
                      "Using compatible package 'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31'",
                      client.out)
        self.assertIn("pkg/0.1:cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31 - Cache", client.out)
        client.run("info pkg/0.1@ -s os=Windows")
        self.assertIn("pkg/0.1: Main binary package 'INVALID' missing. "
                      "Using compatible package 'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31'",
                      client.out)
        self.assertIn("ID: cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31", client.out)
