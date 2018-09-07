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

conanfile_header_only = """
from conans import ConanFile

class AConan(ConanFile):
    name = "Hello0"
    version = "0.1"
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
