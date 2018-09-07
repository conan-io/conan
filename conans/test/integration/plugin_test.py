import unittest

from conans.test.utils.tools import TestClient


conanfile_basic = """
from conans import ConanFile

class AConan(ConanFile):
    name = "basic"
    version = "0.1"
    
    def build(self):
       pass
"""

conanfile_fpic = """
from conans import ConanFile

class AConan(ConanFile):
    name = "fpic"
    version = "0.1"
    options = {"shared": [True, False],
               "fpic": [True, False]}
"""


class PluginTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def default_plugin_test(self):
        self.client.save({"conanfile.py": conanfile_basic})
        self.client.run("export . danimtb/testing")
        self.assertIn("[PLUGIN - RecipeLinter]: WARN: Conanfile doesn't have 'url'",
                      self.client.out)
        self.assertIn("[PLUGIN - RecipeLinter]: WARN: Conanfile doesn't have 'description'",
                      self.client.out)
        self.assertIn("[PLUGIN - RecipeLinter]: WARN: Conanfile doesn't have 'license'",
                      self.client.out)
        self.assertIn("[PLUGIN - RecipeLinter]: WARN: Recipe does not declare 'settings' and has a "
                      "'build()' step", self.client.out)
        self.assertIn("[PLUGIN - RecipeLinter]: WARN: This recipe seems to be for a header only "
                      "library as it does not declare 'settings'. Include 'no_copy_source' to avoid"
                      " unnecessary copy steps", self.client.out)
        self.client.save({"conanfile.py": conanfile_fpic})
        self.client.run("export . danimtb/testing")
        self.assertIn("This recipe has 'shared' or 'fPIC' options but does not declare any "
                      "'settings'", self.client.out)
        conanfile = conanfile_fpic + "    settings = 'os'"
        self.client.save({"conanfile.py": conanfile})
        self.client.run("export . danimtb/testing")
        self.assertIn("This recipe does not include an 'fPIC' option or it does not have the right "
                      "casing to be detected", self.client.out)
