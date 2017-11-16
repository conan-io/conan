import unittest
from conans.test.utils.tools import TestClient


class DevelopTest(unittest.TestCase):

    def develop_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    def requirements(self):
        if self.develop:
            self.output.info("Develop requirements!")
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
        client.save({"conanfile.py": conanfile})
        client.run("create Pkg/0.1@user/testing")
        self.assertIn("Develop requirements!", client.out)
        self.assertIn("Develop build!", client.out)
        self.assertIn("Develop package!", client.out)
        self.assertIn("Develop package_info!", client.out)
        self.assertIn("Develop package_id!", client.out)
