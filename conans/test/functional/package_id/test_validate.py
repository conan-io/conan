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
                        self.info.invalid = True
            """)

        client.save({"conanfile.py": conanfile})

        client.run("create . pkg/0.1@ -s os=Linux")
        self.assertIn("pkg/0.1: Package 'cb054d0b3e1ca595dc66bc2339d40f1f8f04ab31' created",
                      client.out)

        error = client.run("create . pkg/0.1@ -s os=Windows", assert_error=True)
        self.assertEqual(error, ERROR_INVALID_CONFIGURATION)
        self.assertIn("ERROR: pkg/0.1: Invalid ID", client.out)
        client.run("info pkg/0.1@ -s os=Windows")
        print(client.out)
        self.assertIn("ID: INVALID", client.out)
