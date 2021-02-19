import textwrap
import unittest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class InfoOptionsTest(unittest.TestCase):

    def test_info_options(self):
        # packages with dash
        client = TestClient()
        client.save({"conanfile.py":
                         GenConanfile("My-Package", "1.3").with_option("shared", [True, False])
                                                          .with_default_option("shared", False)})
        # assert they are correct at least
        client.run("export . myuser/testing")
        client.run("search")
        self.assertIn("My-Package/1.3@myuser/testing", client.out)

        # Check that I can pass options to info
        client.run("info . -o shared=True")
        self.assertIn("conanfile.py (My-Package/1.3)", client.out)
        client.run("info . -o My-Package:shared=True")
        self.assertIn("conanfile.py (My-Package/1.3)", client.out)

        # errors
        client.run("info . -o shared2=True", assert_error=True)
        self.assertIn("option 'shared2' doesn't exist", client.out)
        client.run("info . -o My-Package:shared2=True", assert_error=True)
        self.assertIn("option 'shared2' doesn't exist", client.out)

    def test_info_wrong_options(self):
        # https://github.com/conan-io/conan/issues/2202
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                options = {{"option{0}1": "ANY", "option{0}2": "ANY"}}
                default_options = "option{0}1=1", "option{0}2=2"
            """)
        client.save({"conanfile.py": conanfile.format("A")})
        client.run("create . PkgA/0.1@user/testing")
        client.save({"conanfile.py": conanfile.format("B")})
        client.run("install .")
        client.run("info PkgA/0.1@user/testing")
        self.assertIn("PkgA/0.1@user/testing", client.out)
        self.assertIn("BuildID: None", client.out)
