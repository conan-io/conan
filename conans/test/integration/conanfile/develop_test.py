import unittest

from parameterized import parameterized

from conans.test.utils.tools import TestClient, GenConanfile

conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    def configure(self):
        self.output.info("Develop %s configure!" % self.develop)
    def requirements(self):
        self.output.info("Develop %s requirements!" % self.develop)
    def source(self):
        self.output.info("Develop %s source!" % self.develop)
    def build(self):
        self.output.info("Develop %s build!" % self.develop)
    def package(self):
        self.output.info("Develop %s package!" % self.develop)
    def package_info(self):
        self.output.info("Develop %s package_info!" % self.develop)
    def package_id(self):
        self.output.info("Develop %s package_id!" % self.develop)
"""


class DevelopTest(unittest.TestCase):

    @parameterized.expand([(True, ), (False, )])
    def test_develop(self, with_test):
        client = TestClient()
        if with_test:
            client.save({"conanfile.py": conanfile})
        else:
            client.save({"conanfile.py": conanfile,
                         "test_package/conanfile.py": GenConanfile().with_test("pass")})
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("Develop True configure!", client.out)
        self.assertIn("Develop True requirements!", client.out)
        self.assertIn("Develop True source!", client.out)
        self.assertIn("Develop True build!", client.out)
        self.assertIn("Develop True package!", client.out)
        self.assertIn("Develop True package_info!", client.out)
        self.assertIn("Develop True package_id!", client.out)

        client.run("install Pkg/0.1@user/testing --build")
        self.assertNotIn("Develop True", client.out)

        client.save({"conanfile.py": GenConanfile().with_require("Pkg/0.1@user/testing")})
        client.run("create . Other/1.0@user/testing")
        self.assertNotIn("Develop True", client.out)

    def test_local_commands(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("install .")
        self.assertIn("Develop True configure!", client.out)
        self.assertIn("Develop True requirements!", client.out)
        self.assertNotIn("source!", client.out)
        self.assertNotIn("build!", client.out)
        self.assertNotIn("package!", client.out)
        self.assertNotIn("package_info!", client.out)
        self.assertIn("Develop True package_id!", client.out)

        client.run("source .")
        self.assertIn("Develop True configure!", client.out)
        self.assertNotIn("requirements!", client.out)
        self.assertIn("Develop True source!", client.out)
        self.assertNotIn("build!", client.out)
        self.assertNotIn("package!", client.out)
        self.assertNotIn("package_info!", client.out)
        self.assertNotIn("package_id!", client.out)

        client.run("build .")
        self.assertIn("Develop True configure!", client.out)
        self.assertNotIn("requirements!", client.out)
        self.assertNotIn("source!", client.out)
        self.assertIn("Develop True build!", client.out)
        self.assertNotIn("package!", client.out)
        self.assertNotIn("package_info!", client.out)
        self.assertNotIn("package_id!", client.out)

        client.run("package .")
        self.assertIn("Develop True configure!", client.out)
        self.assertNotIn("requirements!", client.out)
        self.assertNotIn("source!", client.out)
        self.assertNotIn("build!", client.out)
        self.assertIn("Develop True package!", client.out)
        self.assertNotIn("package_info!", client.out)
        self.assertNotIn("package_id!", client.out)

        client.run("export-pkg . pkg/0.1@user/channel")
        self.assertIn("Develop True configure!", client.out)
        self.assertIn("Develop True requirements!", client.out)
        self.assertNotIn("source!", client.out)
        self.assertNotIn("build!", client.out)
        self.assertIn("Develop True package!", client.out)
        self.assertNotIn("package_info!", client.out)
        self.assertIn("Develop True package_id!", client.out)
