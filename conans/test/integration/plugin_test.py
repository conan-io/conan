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
        self.assertIn("[PLUGIN - recipe_linter] pre_export(): WARN: Conanfile doesn't have 'url'",
                      self.client.out)
        self.assertIn("[PLUGIN - recipe_linter] pre_export(): WARN: Conanfile doesn't have "
                      "'description'", self.client.out)
        self.assertIn("[PLUGIN - recipe_linter] pre_export(): WARN: Conanfile doesn't have "
                      "'license'", self.client.out)
