import unittest
from conans.test.utils.tools import TestClient
from parameterized import parameterized


conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    def requirements(self):
        if self.develop:
            self.output.info("Develop requirements!")
    def source(self):
        if self.develop:
            self.output.info("Develop source!")
    def build(self):
        if self.develop:
            self.output.info("Develop build!")
    def package(self):
        if self.develop:
            self.output.info("Develop package!")
    def package_info(self):
        if self.develop:
            self.output.info("Develop package_info!")
    def package_id(self):
        if self.develop:
            self.output.info("Develop package_id!")
"""


class DevelopTest(unittest.TestCase):

    @parameterized.expand([(True, ), (False, )])
    def develop_test(self, with_test):
        client = TestClient()
        if with_test:
            client.save({"conanfile.py": conanfile})
        else:
            test_conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    def test(self):
        pass
"""
            client.save({"conanfile.py": conanfile,
                         "test_package/conanfile.py": test_conanfile})
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Develop requirements!", client.out)
        self.assertIn("Develop source!", client.out)
        self.assertIn("Develop build!", client.out)
        self.assertIn("Develop package!", client.out)
        self.assertIn("Develop package_info!", client.out)
        self.assertIn("Develop package_id!", client.out)

        client.run("install Pkg/0.1@user/testing --build")
        self.assertNotIn("Develop", client.out)

        consumer = """from conans import ConanFile
class Pkg(ConanFile):
    requires = "Pkg/0.1@user/testing"
"""
        client.save({"conanfile.py": consumer})
        client.run("create . Other/1.0@user/testing")
        self.assertNotIn("Develop", client.out)

    def local_commands_test(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        self.assertIn("Develop requirements!", client.out)
        self.assertNotIn("Develop source!", client.out)
        self.assertNotIn("Develop build!", client.out)
        self.assertNotIn("Develop package!", client.out)
        self.assertNotIn("Develop package_info!", client.out)
        self.assertIn("Develop package_id!", client.out)

        client.run("source .")
        self.assertNotIn("Develop requirements!", client.out)
        self.assertIn("Develop source!", client.out)
        self.assertNotIn("Develop build!", client.out)
        self.assertNotIn("Develop package!", client.out)
        self.assertNotIn("Develop package_info!", client.out)
        self.assertNotIn("Develop package_id!", client.out)

        client.run("build .")
        self.assertNotIn("Develop requirements!", client.out)
        self.assertNotIn("Develop source!", client.out)
        self.assertIn("Develop build!", client.out)
        self.assertNotIn("Develop package!", client.out)
        self.assertNotIn("Develop package_info!", client.out)
        self.assertNotIn("Develop package_id!", client.out)

        client.run("package .")
        self.assertNotIn("Develop requirements!", client.out)
        self.assertNotIn("Develop source!", client.out)
        self.assertNotIn("Develop build!", client.out)
        self.assertIn("Develop package!", client.out)
        self.assertNotIn("Develop package_info!", client.out)
        self.assertNotIn("Develop package_id!", client.out)
