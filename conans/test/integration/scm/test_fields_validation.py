# coding=utf-8

import textwrap
import unittest

from conans.test.utils.tools import TestClient


class SCMDataFieldsValdation(unittest.TestCase):

    def test_fail_string(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Lib(ConanFile):
                scm = {"type": "git", "revision": "123", "username": True}
        """)

        client = TestClient()
        client.save({'conanfile.py': conanfile})
        client.run("export . --name=name --version=version --user=user --channel=channel", assert_error=True)

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
        client.run("export . --name=name --version=version --user=user --channel=channel", assert_error=True)

        self.assertIn("ERROR: SCM value for 'revision' must be of type"
                      " 'str' or 'int' (found 'bool')", client.out)

    def test_fail_boolean(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Lib(ConanFile):
                scm = {"type": "git", "revision": "123", "verify_ssl": "True"}
        """)

        client = TestClient()
        client.save({'conanfile.py': conanfile})
        client.run("export . --name=name --version=version --user=user --channel=channel", assert_error=True)

        self.assertIn("ERROR: SCM value for 'verify_ssl' must be of type 'bool' (found 'str')",
                      client.out)

    def test_ok_none(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Lib(ConanFile):
                scm = {"type": "git", "revision": None, "shallow": False}
        """)

        client = TestClient()
        client.save({'conanfile.py': conanfile})
        client.run("export . --name=name --version=version --user=user --channel=channel")
