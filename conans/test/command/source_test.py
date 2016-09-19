import unittest
from conans.paths import CONANFILE
from conans.test.tools import TestClient


class SourceTest(unittest.TestCase):

    def basic_source_test(self):
        conanfile = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "Hello"
    version = "0.1"
    exports = "*"

    def source(self):
        self.output.info("Running source!")
'''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export lasote/stable")
        client.run("source Hello/0.1@lasote/stable")
        self.assertIn("Hello/0.1@lasote/stable: Configuring sources", client.user_io.out)
        self.assertIn("Hello/0.1@lasote/stable: Running source!", client.user_io.out)

        # The second call shouldn't have effect
        client.run("source Hello/0.1@lasote/stable")
        self.assertNotIn("Hello/0.1@lasote/stable: Configuring sources", client.user_io.out)
        self.assertNotIn("Hello/0.1@lasote/stable: Running source!", client.user_io.out)

        # Forced should have effect
        client.run("source Hello/0.1@lasote/stable --force")
        self.assertIn("WARN: Forced removal of source folder", client.user_io.out)
        self.assertIn("Hello/0.1@lasote/stable: Configuring sources", client.user_io.out)
        self.assertIn("Hello/0.1@lasote/stable: Running source!", client.user_io.out)
