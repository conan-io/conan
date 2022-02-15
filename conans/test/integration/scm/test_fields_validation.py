import textwrap
import unittest

from conans.test.utils.tools import TestClient


class SCMDataFieldsValdation(unittest.TestCase):

    def test_fail_string(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Lib(ConanFile):
                scm = {"type": "git", "revision": "auto", "username": True}
        """)

        client = TestClient()
        client.save({'conanfile.py': conanfile})
        client.run("export . --name=name --version=version --user=user --channel=channel",
                   assert_error=True)

        self.assertIn("ERROR: SCM value for 'username' must be of"
                      " type 'str' (found 'bool')", client.out)

    def test_fail_revision(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Lib(ConanFile):
                scm = {"type": "git", "revision": True}
        """)

        client = TestClient()
        client.save({'conanfile.py': conanfile})
        client.run("export . --name=name --version=version --user=user --channel=channel",
                   assert_error=True)

        self.assertIn("'scm' can only be used for 'auto'", client.out)

    def test_fail_boolean(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Lib(ConanFile):
                scm = {"type": "git", "revision": "auto", "verify_ssl": "True"}
        """)

        client = TestClient()
        client.save({'conanfile.py': conanfile})
        client.run("export . --name=name --version=version --user=user --channel=channel",
                   assert_error=True)

        self.assertIn("ERROR: SCM value for 'verify_ssl' must be of type 'bool' (found 'str')",
                      client.out)
