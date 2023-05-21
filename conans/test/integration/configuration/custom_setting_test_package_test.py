import unittest

from conans.test.utils.tools import TestClient
from conans.util.files import load, save


class ConditionalReqsTest(unittest.TestCase):

    def test_conditional_requirements(self):
        conanfile = """from conan import ConanFile

class TestConanLib(ConanFile):
    name = "hello"
    version = "0.1"
    settings = "os", "build_type", "product"
        """
        test_conanfile = '''
from conan import ConanFile

class TestConanLib(ConanFile):
    settings = "os", "build_type", "product"
    def requirements(self):
        self.output.info("Conditional test requirement: %s, %s, %s"
                         % (self.settings.os, self.settings.build_type, self.settings.product))
        self.requires(self.tested_reference_str)

    def test(self):
        pass
'''
        client = TestClient()
        settings_path = client.cache.settings_path
        client.cache.settings
        settings = load(settings_path)
        settings += "\nproduct: [onion, potato]"
        save(settings_path, settings)
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . --user=lasote --channel=testing -s os=Windows -s product=onion -s build_type=Release")
        self.assertIn("hello/0.1@lasote/testing (test package): Conditional test requirement: "
                      "Windows, Release, onion", client.out)
