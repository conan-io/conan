import unittest

import pytest

from conans.test.utils.tools import TestClient

test_conanfile = """from conan import ConanFile

class test_packageConan(ConanFile):
    name = "conan_test_package"
    options = {"shared": [True, False]}
    default_options = {"shared": False}

    def configure(self):
        self.output.info("shared (configure): %s" % (self.options.shared))
        for package in self.requires:
            self.options[package.split('/', 1)[0]].shared = self.options.shared

    def requirements(self):
        self.output.info("shared (requirements): %s" % (self.options.shared))

    def build(self):
        self.output.info("shared (build): %s" % (self.options.shared))

    def test(self):
        self.output.info("shared (test): %s" % (self.options.shared))
"""


create_conanfile = """from conan import ConanFile

class test_packageConan(ConanFile):
    options = {"shared": [True, False]}
    default_options = {"shared": False}

    def build(self):
        self.output.info("shared (build): %s" % (self.options["conan_package"].shared))

    def test(self):
        self.output.info("shared (test): %s" % (self.options["conan_package"].shared))
"""


conanfile = """from conan import ConanFile

class PkgConan(ConanFile):
    name = "conan_package"
    version = "0.1"
    options = {"shared": [True, False]}
    default_options = {"shared": False}

    def configure(self):
        self.output.info("shared (configure): %s" % str(self.options.shared))

    def requirements(self):
        self.output.info("shared (requirements): %s" % str(self.options.shared))

    def build(self):
        self.output.info("shared (build): %s" % str(self.options.shared))
"""


@pytest.mark.xfail(reason="Test package will not allow option configuration, it breaks everything")
class TestPackageConfigTest(unittest.TestCase):

    def test_test_package(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . --user=lasote --channel=stable -o conan_test_package:shared=True")
        self.assertIn("conan_package/0.1@lasote/stable (test package): shared (configure): True",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable (test package): shared (requirements): True",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable: shared (configure): True",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable: shared (configure): True",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable (test package): shared (build): True",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable (test package): shared (test): True",
                      client.out)
        #self.assertNotIn("False", client.out)

        client.run("create . --user=lasote --channel=stable -o conan_test_package:shared=False")
        self.assertIn("conan_package/0.1@lasote/stable (test package): shared (configure): False",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable (test package): shared (requirements): False",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable: shared (configure): False",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable: shared (configure): False",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable (test package): shared (build): False",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable (test package): shared (test): False",
                      client.out)
        #self.assertNotIn("True", client.out)

    def test_create(self):
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": create_conanfile})
        client.run("create . --user=lasote --channel=stable -o conan_package:shared=True")
        self.assertIn("conan_package/0.1@lasote/stable: shared (configure): True",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable: shared (configure): True",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable (test package): shared (build): True",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable (test package): shared (test): True",
                      client.out)
        #self.assertNotIn("False", client.out)

        client.run("create . --user=lasote --channel=stable -o shared=False")
        self.assertIn("conan_package/0.1@lasote/stable: shared (configure): False",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable: shared (configure): False",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable (test package): shared (build): False",
                      client.out)
        self.assertIn("conan_package/0.1@lasote/stable (test package): shared (test): False",
                      client.out)
        #self.assertNotIn("True", client.out)
