import unittest
from conans.test.utils.tools import TestClient


class InfoOptionsTest(unittest.TestCase):

    def info_options_test(self):
        """ packages with dash
        """
        client = TestClient()
        client.run('new My-Package/1.3@myuser/testing -t')
        # assert they are correct at least
        client.run("export . myuser/testing")
        client.run("search")
        self.assertIn("My-Package/1.3@myuser/testing", client.user_io.out)

        # Check that I can pass options to info
        client.run("info . -o shared=True")
        self.assertIn("My-Package/1.3@PROJECT", client.user_io.out)
        client.run("info . -o My-Package:shared=True")
        self.assertIn("My-Package/1.3@PROJECT", client.user_io.out)

        # errors
        client.run("info . -o shared2=True", ignore_error=True)
        self.assertIn("'options.shared2' doesn't exist", client.user_io.out)
        client.run("info . -o My-Package:shared2=True", ignore_error=True)
        self.assertIn("'options.shared2' doesn't exist", client.user_io.out)

    def info_wrong_options_test(self):
        # https://github.com/conan-io/conan/issues/2202
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    options = {{"option{0}1": "ANY", "option{0}2": "ANY"}}
    default_options = "option{0}1=1", "option{0}2=2"
"""
        client.save({"conanfile.py": conanfile.format("A")})
        client.run("create . PkgA/0.1@user/testing")
        client.save({"conanfile.py": conanfile.format("B")})
        client.run("install .")
        client.run("info PkgA@0.1@user/testing")
        self.assertIn("PkgA/0.1@user/testing", client.out)
        self.assertIn("BuildID: None", client.out)
