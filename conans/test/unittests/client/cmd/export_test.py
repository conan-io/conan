import unittest
from conans.test.utils.tools import TestClient


class ExportTest(unittest.TestCase):

    def test_export_warning(self):
        mixed_conanfile = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*.h", "*.cpp"
    settings = "os", "os_build"
    def package(self):
        self.copy("*.h", "include")
"""
        client = TestClient()
        client.save({"conanfile.py": mixed_conanfile})
        client.run("export . Hello/0.1")
        self.assertIn("This package defines both 'os' and 'os_build'", client.out)

    def test_export_no_warning(self):
        conanfile = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*.h", "*.cpp"
    settings = "os"
    def package(self):
        self.copy("*.h", "include")
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . Hello/0.1")
        self.assertNotIn("This package defines both 'os' and 'os_build'", client.out)
