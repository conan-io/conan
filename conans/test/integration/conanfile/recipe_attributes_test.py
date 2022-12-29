import textwrap
import unittest

from conans.test.utils.tools import TestClient


class TestRecipeAttribute(unittest.TestCase):

    def test_invalid_description(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
                from conans import ConanFile
                class Pkg(ConanFile):
                    description = ("foo", "bar")
                """)
        client.save({"conanfile.py": conanfile})
        client.run("create . pkg/0.1@user/testing", assert_error=True)

        self.assertIn("Recipe 'description' must be a string.", client.out)
