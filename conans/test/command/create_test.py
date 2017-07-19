from conans.test.utils.tools import TestClient
import unittest


class CreateTest(unittest.TestCase):

    def create_test(self):
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    def source(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def configure(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def requirements(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def build(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def package(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
    def package_info(self):
        assert(self.version=="0.1")
        assert(self.name=="Pkg")
"""})
        client.run("create Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Generating the package", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/testing", client.out)

    def test_error_create_name_version(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "1.2"
"""
        client.save({"conanfile.py": conanfile})
        client.run("create Hello/1.2@lasote/stable")
        error = client.run("create Pkg/1.2@lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Package recipe exported with name Pkg!=Hello", client.out)
        error = client.run("create Hello/1.1@lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Package recipe exported with version 1.1!=1.2", client.out)

    def create_user_channel_test(self):
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    name = "Pkg"
    version = "0.1"
"""})
        client.run("create lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Generating the package", client.out)
        client.run("search")
        self.assertIn("Pkg/0.1@lasote/testing", client.out)

    def create_test_package_test(self):
        client = TestClient()
        client.save({"conanfile.py": """from conans import ConanFile
class MyPkg(ConanFile):
    name = "Pkg"
    version = "0.1"
""", "test_package/conanfile.py": """from conans import ConanFile
class MyTest(ConanFile):
    def test(self):
        self.output.info("TESTING!!!")
"""})
        client.run("create lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Generating the package", client.out)
        self.assertIn("Pkg/0.1@lasote/testing test package: TESTING!!!", client.out)
